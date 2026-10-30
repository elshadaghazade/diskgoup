"""``diskgoup serve`` — the JSON-RPC server the Electron app talks to.

The GUI drives the CLI through this channel rather than through the terminal
commands, because it needs two things the CLI's one-shot output cannot give
it: **progress notifications** during a long scan, and **structured results**
without re-parsing human-formatted text.

Protocol: newline-delimited JSON on stdin/stdout.

Request::

    {"id": 1, "method": "explore.tree", "params": {"path": "/Users/me"}}

Response::

    {"id": 1, "result": {...}}
    {"id": 1, "error": {"code": -32000, "message": "path does not exist"}}

Server-initiated notification (no ``id``)::

    {"method": "scan.progress", "params": {"files": 1200, "bytes": 3400000}}

``scan.run`` runs on a worker thread, so the loop keeps reading while a scan
is in progress. That is what lets the GUI pause it: ``scan.pause``,
``scan.resume`` and ``scan.cancel`` act on the running scan.

Anything written to stdout that is not a JSON line is protocol noise, so the
server redirects stray output to stderr.
"""

from __future__ import annotations

import json
import sys
import threading
import time
import traceback
from collections.abc import Callable
from pathlib import Path
from typing import Any

import typer

from diskgoup import __version__

#: JSON-RPC error codes.
PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INTERNAL_ERROR = -32603

Handler = Callable[[dict[str, Any], "Server"], Any]


class Server:
    """Dispatches JSON-RPC requests to the CLI's core."""

    def __init__(self) -> None:
        self.handlers: dict[str, Handler] = {}
        # The control of the scan that is running right now, if any. The GUI
        # pauses and stops a scan through it.
        self._scan_control: Any = None
        self._scan_lock = threading.Lock()
        self._register()

    # ------------------------------------------------------------------ setup

    def _register(self) -> None:
        self.handlers.update(
            {
                "app.info": self._app_info,
                "app.ping": self._ping,
                "drives.list": self._drives_list,
                "scans.list": self._scans_list,
                "scans.remove": self._scans_remove,
                "scan.run": self._scan_run,
                "scan.pause": self._scan_pause,
                "scan.resume": self._scan_resume,
                "scan.cancel": self._scan_cancel,
                "explore.tree": self._explore_tree,
                "explore.children": self._explore_children,
                "explore.sizes": self._explore_sizes,
                "explore.types": self._explore_types,
                "explore.age": self._explore_age,
                "view.layout": self._view_layout,
                "search.query": self._search_query,
                "duplicates.find": self._duplicates_find,
                "archives.list": self._archives_list,
                "archives.preview": self._archives_preview,
                "games.list": self._games_list,
                "apps.list": self._apps_list,
                "monitor.sample": self._monitor_sample,
                "snapshots.list": self._snapshots_list,
                "snapshots.save": self._snapshots_save,
                "snapshots.compare": self._snapshots_compare,
                "reports.weekly": self._reports_weekly,
                "reports.types": self._reports_types,
                "cleanup.stage": self._cleanup_stage,
                "cleanup.unstage": self._cleanup_unstage,
                "cleanup.list": self._cleanup_list,
                "cleanup.validate": self._cleanup_validate,
                "cleanup.commit": self._cleanup_commit,
            }
        )

    # ------------------------------------------------------------- dispatching

    def handle(self, request: dict[str, Any]) -> dict[str, Any] | None:
        """Handle one request. Returns the response, or ``None`` for a notification."""
        request_id = request.get("id")
        method = request.get("method")
        params = request.get("params") or {}

        if not isinstance(method, str):
            return self._error(request_id, INVALID_REQUEST, "method must be a string")

        handler = self.handlers.get(method)
        if handler is None:
            if request_id is None:
                return None
            return self._error(request_id, METHOD_NOT_FOUND, f"unknown method: {method}")

        try:
            result = handler(params, self)
        except Exception as exc:
            if request_id is None:
                return None
            return self._error(request_id, INTERNAL_ERROR, str(exc))

        if request_id is None:
            return None
        return {"id": request_id, "result": result}

    @staticmethod
    def _error(request_id: Any, code: int, message: str) -> dict[str, Any]:
        return {"id": request_id, "error": {"code": code, "message": message}}

    def notify(self, method: str, params: Any) -> None:
        """Send a notification to the client."""
        _write({"method": method, "params": params})

    # ------------------------------------------------------------ background

    def dispatch_background(self, request: dict[str, Any]) -> bool:
        """Run ``scan.run`` on a worker thread so the read loop keeps going.

        The GUI has to be able to pause a scan, and the request that does it
        can only be read while the scan is still running. So the scan runs off
        the loop and its response is written when it finishes.

        Returns ``True`` when the request was handed to a worker.
        """
        if request.get("method") != "scan.run" or request.get("id") is None:
            return False
        threading.Thread(target=self._run_background, args=(request,), daemon=True).start()
        return True

    def _run_background(self, request: dict[str, Any]) -> None:
        """Handle one request on a worker thread and write its response."""
        try:
            response = self.handle(request)
        except Exception:
            traceback.print_exc(file=sys.stderr)
            response = Server._error(request.get("id"), INTERNAL_ERROR, "internal error")
        if response is not None:
            _write(response)

    # --------------------------------------------------------------- helpers

    def _index(self) -> Any:
        from diskgoup.core.store import ScanIndex

        return ScanIndex()

    def _scan_for(self, index: Any, params: dict[str, Any]) -> Any:
        from diskgoup.commands.common import ensure_scan

        return ensure_scan(
            index,
            params.get("path"),
            scan_id=params.get("scan_id"),
            rescan=bool(params.get("rescan", False)),
            show_progress=False,
        )

    # ---------------------------------------------------------------- methods

    def _app_info(self, params: dict[str, Any], server: Server) -> dict[str, Any]:
        from diskgoup.core.partitions import volumes

        return {
            "version": __version__,
            "platform": sys.platform,
            "volumes": [volume.to_dict() for volume in volumes()],
        }

    def _ping(self, params: dict[str, Any], server: Server) -> dict[str, Any]:
        return {"pong": True}

    def _drives_list(self, params: dict[str, Any], server: Server) -> dict[str, Any]:
        from diskgoup.core.partitions import volumes

        return {"volumes": [volume.to_dict() for volume in volumes()]}

    def _scans_list(self, params: dict[str, Any], server: Server) -> dict[str, Any]:
        with self._index() as index:
            return {"scans": [meta.to_dict() for meta in index.scans()]}

    def _scans_remove(self, params: dict[str, Any], server: Server) -> dict[str, Any]:
        """Remove a scan and everything recorded for it from the index."""
        raw = params.get("scan_id")
        if raw is None:
            raise ValueError("scan_id is required")
        scan_id = int(raw)

        with self._index() as index:
            meta = index.scan_meta(scan_id)
            if meta is None:
                raise ValueError(f"no scan with id {scan_id}")
            index.delete_scan(scan_id)
            return {"removed": meta.to_dict()}

    def _scan_run(self, params: dict[str, Any], server: Server) -> dict[str, Any]:
        from pathlib import Path

        from diskgoup.core.scanner import ScanControl, Scanner, ScanOptions

        root = params.get("path")
        if not root:
            return {"error": "path is required"}

        with self._index() as index:
            control = ScanControl()
            with self._scan_lock:
                if self._scan_control is not None:
                    raise RuntimeError("a scan is already running")
                self._scan_control = control

            try:
                scanner = Scanner(
                    index,
                    ScanOptions(
                        root=Path(root),
                        follow_symlinks=bool(params.get("follow_symlinks", False)),
                        include_hidden=bool(params.get("include_hidden", True)),
                        exclude=tuple(params.get("exclude") or ()),
                        max_depth=params.get("max_depth"),
                    ),
                )

                last = 0.0

                def on_progress(progress: Any) -> None:
                    # One notification per file would flood the pipe — the GUI
                    # only needs a steady stream of updates.
                    nonlocal last
                    now = time.monotonic()
                    if now - last < 0.1:
                        return
                    last = now
                    server.notify("scan.progress", progress.to_dict())

                result = scanner.run(on_progress, control=control)
                return result.to_dict()
            finally:
                with self._scan_lock:
                    self._scan_control = None

    def _running_scan(self) -> Any:
        """The control of the running scan, if there is one."""
        with self._scan_lock:
            control = self._scan_control
        if control is None:
            raise RuntimeError("no scan is running")
        return control

    def _scan_pause(self, params: dict[str, Any], server: Server) -> dict[str, Any]:
        control = self._running_scan()
        control.pause()
        server.notify("scan.state", {"state": "paused"})
        return {"paused": True}

    def _scan_resume(self, params: dict[str, Any], server: Server) -> dict[str, Any]:
        control = self._running_scan()
        control.resume()
        server.notify("scan.state", {"state": "running"})
        return {"paused": False}

    def _scan_cancel(self, params: dict[str, Any], server: Server) -> dict[str, Any]:
        control = self._running_scan()
        control.cancel()
        server.notify("scan.state", {"state": "canceled"})
        return {"canceled": True}

    def _explore_tree(self, params: dict[str, Any], server: Server) -> dict[str, Any]:
        with self._index() as index:
            meta = self._scan_for(index, params)
            root = index.build_tree(meta.scan_id)
            return {"scan": meta.to_dict(), "tree": root.to_dict() if root else None}

    def _explore_children(self, params: dict[str, Any], server: Server) -> dict[str, Any]:
        """List what is inside one folder of a scan.

        The listing comes from the index, so browsing a folder never re-walks
        the disk. The scan is pinned by ``scan_id``; the path is only the folder
        to open.
        """
        with self._index() as index:
            meta = self._scan_for(index, params)
            root = Path(meta.root)
            target = Path(params.get("path") or meta.root)

            row = index.entry_by_path(meta.scan_id, target)
            if row is None:
                raise ValueError(f"{target} is not in scan #{meta.scan_id}")

            entries: list[dict[str, Any]] = [
                {
                    "name": str(child["name"]),
                    "path": str(child["path"]),
                    "is_dir": bool(child["is_dir"]),
                    "size": int(child["size"]),
                    "on_disk": int(child["on_disk"]),
                    "kind": str(child["kind"]),
                    "protected": bool(child["protected"]),
                    "mtime": float(child["mtime"]),
                    "files": int(child["file_count"]),
                    "folders": int(child["dir_count"]),
                }
                for child in index.children(meta.scan_id, int(row["id"]))
            ]
            # Folders first, then files — each group by size, the way a file
            # manager shows them.
            entries.sort(key=lambda entry: (not entry["is_dir"], -entry["size"], entry["name"]))

            path = str(row["path"])
            return {
                "scan": meta.to_dict(),
                "path": path,
                "parent": _parent_path(root, path),
                "crumbs": _crumbs(root, path),
                "entries": entries,
            }

    def _explore_sizes(self, params: dict[str, Any], server: Server) -> dict[str, Any]:
        from diskgoup.util.humanize import human_bytes

        with self._index() as index:
            meta = self._scan_for(index, params)
            rows = index.largest_entries(
                meta.scan_id,
                limit=int(params.get("limit", 50)),
                folders=bool(params.get("folders", True)),
                files=bool(params.get("files", True)),
            )
            total = meta.total_size or 1
            return {
                "scan": meta.to_dict(),
                "entries": [
                    {
                        "name": row["name"],
                        "path": row["path"],
                        "is_dir": bool(row["is_dir"]),
                        "size": int(row["size"]),
                        "size_human": human_bytes(int(row["size"])),
                        "on_disk": int(row["on_disk"]),
                        "kind": row["kind"],
                        "protected": bool(row["protected"]),
                        "share": int(row["size"]) / total,
                    }
                    for row in rows
                ],
            }

    def _explore_types(self, params: dict[str, Any], server: Server) -> dict[str, Any]:
        from diskgoup.core.models import KIND_ORDER

        with self._index() as index:
            meta = self._scan_for(index, params)
            totals = index.kind_totals(meta.scan_id)
            counts = index.kind_counts(meta.scan_id)
            total = sum(totals.values()) or 1
            ordered = [
                (kind, totals.get(str(kind), 0), counts.get(str(kind), 0))
                for kind in KIND_ORDER
                if totals.get(str(kind), 0) or counts.get(str(kind), 0)
            ]
            return {
                "scan": meta.to_dict(),
                "types": [
                    {
                        "kind": str(kind),
                        "size": size,
                        "files": count,
                        "share": size / total,
                    }
                    for kind, size, count in ordered
                ],
            }

    def _explore_age(self, params: dict[str, Any], server: Server) -> dict[str, Any]:
        from diskgoup.core.views import age_view

        with self._index() as index:
            meta = self._scan_for(index, params)
            buckets = age_view(index.files_with_mtime(meta.scan_id))
            total = sum(bucket.size for bucket in buckets) or 1
            return {
                "scan": meta.to_dict(),
                "buckets": [
                    {**bucket.to_dict(), "share": bucket.size / total} for bucket in buckets
                ],
            }

    def _view_layout(self, params: dict[str, Any], server: Server) -> dict[str, Any]:
        from diskgoup.core.render import color_for
        from diskgoup.core.views import (
            bubbles_view,
            build_layout,
            flame_view,
            mindmap_view,
            sunburst_view,
            treemap_view,
        )

        view = str(params.get("view", "treemap"))
        depth = int(params.get("depth", 3))

        with self._index() as index:
            meta = self._scan_for(index, params)
            root = index.build_tree(meta.scan_id)
            if root is None:
                return {"scan": meta.to_dict(), "items": []}

            layout = build_layout(root, max_depth=depth)
            if view == "treemap":
                nodes = treemap_view(layout, depth=depth)
            elif view == "sunburst":
                nodes = sunburst_view(layout, depth=depth)
            elif view == "flame":
                nodes = flame_view(layout, depth=depth)
            elif view == "bubbles":
                nodes = bubbles_view(layout, depth=depth)
            else:
                nodes = mindmap_view(layout, depth=depth)

            items = []
            for node in nodes:
                entry: dict[str, Any] = {
                    "path": node.path,
                    "name": node.name,
                    "size": node.size,
                    "kind": node.kind,
                    "depth": node.depth,
                    "color": color_for(node),
                    "parent_path": node.parent_path,
                }
                if node.rect is not None:
                    entry["rect"] = node.rect.to_dict()
                if view == "sunburst":
                    entry["start_angle"] = node.start_angle
                    entry["end_angle"] = node.end_angle
                    entry["radius"] = node.radius
                if view in {"flame", "bubbles", "mindmap"}:
                    entry["x"] = node.x
                    entry["y"] = node.y
                    entry["radius"] = node.radius
                items.append(entry)

            return {"scan": meta.to_dict(), "view": view, "items": items}

    def _search_query(self, params: dict[str, Any], server: Server) -> dict[str, Any]:
        from diskgoup.core.search import SearchQuery, parse_date, parse_size, search

        query = SearchQuery(
            name=params.get("name"),
            path=params.get("path_filter"),
            extensions=tuple(params.get("extensions") or ()),
            entry_type=str(params.get("entry_type", "any")),
            kinds=tuple(params.get("kinds") or ()),
            from_date=parse_date(params["from_date"]) if params.get("from_date") else None,
            to_date=parse_date(params["to_date"]) if params.get("to_date") else None,
            min_size=parse_size(params["min_size"]) if params.get("min_size") else None,
            max_size=parse_size(params["max_size"]) if params.get("max_size") else None,
            min_age_days=params.get("min_age_days"),
            max_age_days=params.get("max_age_days"),
            protected_only=bool(params.get("protected_only", False)),
        )

        with self._index() as index:
            meta = self._scan_for(index, params)
            result = search(
                index.connection,
                meta.scan_id,
                query,
                page=int(params.get("page", 1)),
                per_page=int(params.get("per_page", 200)),
            )
            return {"scan": meta.to_dict(), **result.to_dict()}

    def _duplicates_find(self, params: dict[str, Any], server: Server) -> dict[str, Any]:
        from pathlib import Path

        from diskgoup.core.duplicates import find_duplicates

        with self._index() as index:
            meta = self._scan_for(index, params)
            candidates = [
                Path(row["path"]) for row in index.iter_entries(meta.scan_id) if not row["is_dir"]
            ]

            def on_progress(message: str) -> None:
                server.notify("duplicates.progress", {"stage": message})

            report = find_duplicates(candidates, progress=on_progress)
            return {"scan": meta.to_dict(), **report.to_dict()}

    def _archives_list(self, params: dict[str, Any], server: Server) -> dict[str, Any]:
        from pathlib import Path

        from diskgoup.core.archives import list_archive

        archive = params.get("archive")
        if not archive:
            return {"error": "archive is required"}
        return list_archive(Path(archive), prefix=str(params.get("prefix", ""))).to_dict()

    def _archives_preview(self, params: dict[str, Any], server: Server) -> dict[str, Any]:
        from pathlib import Path

        from diskgoup.core.archives import preview

        archive = params.get("archive")
        member = params.get("member")
        if not archive or not member:
            return {"error": "archive and member are required"}
        return preview(Path(archive), str(member)).to_dict()

    def _games_list(self, params: dict[str, Any], server: Server) -> dict[str, Any]:
        from diskgoup.core.games import discover

        libraries = discover()
        return {
            "libraries": [library.to_dict() for library in libraries],
            "total_size": sum(game.size for library in libraries for game in library.games),
        }

    def _apps_list(self, params: dict[str, Any], server: Server) -> dict[str, Any]:
        from diskgoup.core.applications import discover

        return discover().to_dict()

    def _monitor_sample(self, params: dict[str, Any], server: Server) -> dict[str, Any]:
        from diskgoup.core.monitor import Monitor

        return Monitor().sample(process_count=int(params.get("processes", 10))).to_dict()

    def _snapshots_list(self, params: dict[str, Any], server: Server) -> dict[str, Any]:
        from diskgoup.core.snapshots import list_snapshots

        with self._index() as index:
            meta = self._scan_for(index, params)
            return {
                "scan": meta.to_dict(),
                "snapshots": [s.to_dict() for s in list_snapshots(index, meta.scan_id)],
            }

    def _snapshots_save(self, params: dict[str, Any], server: Server) -> dict[str, Any]:
        from diskgoup.core.snapshots import save

        with self._index() as index:
            meta = self._scan_for(index, params)
            return save(index, meta.scan_id, params.get("label")).to_dict()

    def _snapshots_compare(self, params: dict[str, Any], server: Server) -> dict[str, Any]:
        from diskgoup.core.snapshots import compare

        with self._index() as index:
            meta = self._scan_for(index, params)
            comparison = compare(
                index,
                meta.scan_id,
                min_age_days=float(params.get("min_age_days", 7.0)),
            )
            return comparison.to_dict()

    def _reports_weekly(self, params: dict[str, Any], server: Server) -> dict[str, Any]:
        from diskgoup.core.reports import build_weekly_report, weekly_report_html

        with self._index() as index:
            meta = self._scan_for(index, params)
            report = build_weekly_report(index, meta.scan_id)
            return {"scan": meta.to_dict(), "html": weekly_report_html(report)}

    def _reports_types(self, params: dict[str, Any], server: Server) -> dict[str, Any]:
        from diskgoup.core.reports import type_report_csv

        with self._index() as index:
            meta = self._scan_for(index, params)
            return {"scan": meta.to_dict(), "csv": type_report_csv(index, meta.scan_id)}

    def _cleanup_stage(self, params: dict[str, Any], server: Server) -> dict[str, Any]:
        from pathlib import Path

        from diskgoup.core.cleanup import stage

        with self._index() as index:
            meta = self._scan_for(index, params)
            paths = [Path(p) for p in params.get("paths", [])]
            added, refused = stage(index, meta.scan_id, paths)
            return {
                "scan": meta.to_dict(),
                "staged": [item.to_dict() for item in added],
                "refused": [issue.to_dict() for issue in refused],
            }

    def _cleanup_unstage(self, params: dict[str, Any], server: Server) -> dict[str, Any]:
        """Take items back off the review list."""
        from diskgoup.core.cleanup import unstage

        with self._index() as index:
            meta = self._scan_for(index, params)
            paths = [Path(p) for p in params.get("paths", [])]
            return {"scan": meta.to_dict(), "removed": unstage(index, meta.scan_id, paths)}

    def _cleanup_list(self, params: dict[str, Any], server: Server) -> dict[str, Any]:
        from diskgoup.core.cleanup import staged_items

        with self._index() as index:
            meta = self._scan_for(index, params)
            items = staged_items(index, meta.scan_id)
            return {
                "scan": meta.to_dict(),
                "items": [item.to_dict() for item in items],
                "total": sum(item.size for item in items),
            }

    def _cleanup_validate(self, params: dict[str, Any], server: Server) -> dict[str, Any]:
        from diskgoup.core.cleanup import validate

        with self._index() as index:
            meta = self._scan_for(index, params)
            valid, issues = validate(index, meta.scan_id)
            return {
                "scan": meta.to_dict(),
                "valid": [item.to_dict() for item in valid],
                "issues": [issue.to_dict() for issue in issues],
            }

    def _cleanup_commit(self, params: dict[str, Any], server: Server) -> dict[str, Any]:
        from diskgoup.core.cleanup import commit

        with self._index() as index:
            meta = self._scan_for(index, params)
            result = commit(
                index,
                meta.scan_id,
                to_trash=not bool(params.get("permanent", False)),
                permanent=bool(params.get("permanent", False)),
            )
            return {"scan": meta.to_dict(), **result.to_dict()}


def _parent_path(root: Path, path: str) -> str | None:
    """The folder one level up, or ``None`` when the folder is the scan root."""
    if Path(path) == root:
        return None
    return str(Path(path).parent)


def _crumbs(root: Path, path: str) -> list[dict[str, str]]:
    """The ancestor chain of a folder, from the scan root down to it.

    This is what the GUI shows as a breadcrumb: every step is a path that can
    be opened again.
    """
    crumbs: list[dict[str, str]] = []
    current = Path(path)
    while True:
        crumbs.append({"name": current.name or str(current), "path": str(current)})
        if current == root:
            break
        parent = current.parent
        if parent == current:
            break
        current = parent
    crumbs.reverse()
    return crumbs


#: Guards stdout: the read loop and the scan worker both write to it.
_WRITE_LOCK = threading.Lock()


def _write(payload: dict[str, Any]) -> None:
    """Write one JSON line to stdout."""
    line = json.dumps(payload, ensure_ascii=False, default=str) + "\n"
    with _WRITE_LOCK:
        sys.stdout.write(line)
        sys.stdout.flush()


def serve_command(
    quiet: bool = typer.Option(False, "--quiet", help="Suppress the startup banner."),
) -> None:
    """Run the JSON-RPC server on stdin/stdout."""
    server = Server()

    if not quiet:
        # The banner goes to stderr: stdout is reserved for protocol traffic.
        print(f"diskgoup {__version__} — JSON-RPC server ready", file=sys.stderr, flush=True)

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
        except json.JSONDecodeError as exc:
            _write(Server._error(None, PARSE_ERROR, f"invalid JSON: {exc}"))
            continue
        if not isinstance(request, dict):
            _write(Server._error(None, INVALID_REQUEST, "request must be an object"))
            continue

        # A scan runs on a worker thread so that this loop keeps reading and
        # the GUI can pause it while it is running.
        if server.dispatch_background(request):
            continue

        try:
            response = server.handle(request)
        except Exception:
            traceback.print_exc(file=sys.stderr)
            response = Server._error(request.get("id"), INTERNAL_ERROR, "internal error")

        if response is not None:
            _write(response)


def register(app: typer.Typer) -> None:
    """Register the serve command on the root application."""
    app.command("serve")(serve_command)
