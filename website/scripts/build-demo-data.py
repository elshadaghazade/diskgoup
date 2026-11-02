#!/usr/bin/env python3
"""Build the sample disk the website's interactive demo runs on.

The demo is not hand-written mock data. A synthetic disk is created, the
**real** DiskGOup CLI scans it, and the JSON-RPC payloads the desktop app
consumes are collected over ``diskgoup serve``. What lands in
``website/public/demo.json`` is therefore exactly what the real app would
show for that disk — the same layout maths, the same colours, the same
duplicate detection.

Run it from the repository root::

    uv run python website/scripts/build-demo-data.py

Nothing outside ``/tmp`` is written, and the scan index used is a throwaway
one — the index of the real app is never touched.
"""

from __future__ import annotations

import json
import os
import random
import shutil
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
DISK = Path("/tmp/diskgoup-demo-disk")
INDEX = Path("/tmp/diskgoup-demo-index/index.db")
OUT = REPO / "website" / "public" / "demo.json"

#: The path the demo shows. The real one is a temp directory, so it is
#: rewritten to something a reader recognises as a home directory.
SHOWN_ROOT = "/Users/demo"

SEED = 20261102


# ───────────────────────────────────────────────────────────── the sample disk ──


def write_file(path: Path, size: float, rng: random.Random, age_days: float | None = None) -> None:
    """Create a file of the given apparent size.

    The files are sparse — the size is what the scanner reads, the disk
    holds almost nothing. A 9 GB movie costs no space here.

    ``age_days`` sets the modification time, so the age map of the demo has
    something to show: a disk where every file was written today is not a
    disk anyone has.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    size = int(size)
    if size < 4 * 1024 * 1024:
        path.write_bytes(rng.randbytes(size))
    else:
        with path.open("wb") as handle:
            handle.truncate(size)
    if age_days is not None:
        stamp = time.time() - age_days * 86400
        os.utime(path, (stamp, stamp))
    else:
        stamp = time.time() - pick_age(rng) * 86400
        os.utime(path, (stamp, stamp))


#: Where a file's age lands, weighted the way a real disk looks: most of it
#: is recent, a stubborn minority is years old.
AGE_WEIGHTS = ((0.5, 1, 30), (0.25, 30, 120), (0.15, 120, 400), (0.10, 400, 1200))


def pick_age(rng: random.Random) -> float:
    roll = rng.random()
    edge = 0.0
    for weight, low, high in AGE_WEIGHTS:
        edge += weight
        if roll <= edge:
            return rng.uniform(low, high)
    return rng.uniform(1, 30)


def build_disk(rng: random.Random) -> None:
    if DISK.exists():
        shutil.rmtree(DISK)

    # Applications — the biggest single chunk on a real machine.
    apps = {
        "Xcode": 8.4e9,
        "Adobe Photoshop 2025": 4.1e9,
        "Firefox": 1.2e9,
        "Slack": 0.9e9,
        "Visual Studio Code": 0.7e9,
        "Spotify": 0.42e9,
        "Zoom": 0.31e9,
        "Figma": 0.28e9,
        "Blender": 0.66e9,
    }
    for name, size in apps.items():
        folder = DISK / "Applications" / f"{name}.app" / "Contents"
        write_file(folder / "MacOS" / name, size, rng)
        write_file(folder / "Resources" / "app.asar", size * 0.04, rng)
        for index in range(6):
            write_file(
                folder / "Frameworks" / f"framework-{index}.dylib",
                rng.uniform(4e6, 40e6),
                rng,
            )

    # Documents — small, many, text-heavy.
    for index in range(70):
        folder = rng.choice(["Work", "Invoices", "Notes", "Archive"])
        write_file(
            DISK / "Documents" / folder / f"document-{index:03d}.pdf",
            rng.uniform(40e3, 8e6),
            rng,
        )

    # Downloads — installers, archives and the usual leftovers.
    for index in range(26):
        kind = rng.choice(["dmg", "zip", "pdf", "mov"])
        write_file(
            DISK / "Downloads" / f"download-{index:02d}.{kind}",
            rng.uniform(1e6, 900e6),
            rng,
        )

    # Movies, music and pictures.
    for index in range(12):
        write_file(
            DISK / "Movies" / f"clip-{index:02d}.mp4",
            rng.uniform(1.2e9, 9.4e9),
            rng,
        )
    for index in range(44):
        write_file(
            DISK / "Music" / f"track-{index:02d}.mp3",
            rng.uniform(4e6, 12e6),
            rng,
        )
    for index in range(130):
        write_file(
            DISK / "Pictures" / f"photo-{index:03d}.jpg",
            rng.uniform(0.8e6, 12e6),
            rng,
        )

    # The caches the system regenerates — this is what "safe to clean" finds.
    caches = {
        "Library/Caches/com.apple.Safari": 1.9e9,
        "Library/Caches/pip": 4.6e9,
        "Library/Caches/Homebrew": 2.2e9,
        "Library/Caches/ms-playwright": 3.1e9,
        "Library/Caches/com.docker.docker": 1.3e9,
    }
    for folder, size in caches.items():
        parts = 40
        for index in range(parts):
            write_file(
                DISK / folder / f"blob-{index:03d}.bin",
                size / parts * rng.uniform(0.4, 1.6),
                rng,
            )

    # Logs — small, but plenty of them.
    for index in range(30):
        write_file(
            DISK / "Library/Logs" / f"service-{index:02d}.log",
            rng.uniform(20e3, 900e3),
            rng,
        )

    # Application data.
    for index in range(40):
        write_file(
            DISK / "Library/Application Support" / f"vendor-{index:02d}" / "state.db",
            rng.uniform(1e6, 220e6),
            rng,
        )

    # A project tree, with the node_modules every developer recognises.
    write_file(DISK / "Projects/website/package.json", 2_400, rng)
    for index in range(28):
        write_file(
            DISK / "Projects/website/src" / f"module-{index:02d}.ts",
            rng.uniform(1e3, 24e3),
            rng,
        )
    for index in range(180):
        write_file(
            DISK / "Projects/website/node_modules" / f"package-{index:03d}" / "index.js",
            rng.uniform(3e3, 400e3),
            rng,
        )

    # A game library.
    for name, size in {"Elden Ring": 42e9, "Hades": 9e9, "Stardew Valley": 2e9}.items():
        write_file(DISK / "Games/Steam/steamapps/common" / name / "game.bin", size, rng)

    # Three groups of byte-identical files — the duplicate finder finds them
    # by SHA-256, exactly as it does on a real disk.
    groups = [
        ("presentation-final.pdf", ["Documents/Work", "Downloads", "Desktop"]),
        ("invoice-2026-04.pdf", ["Documents/Invoices", "Downloads"]),
        ("backup-archive.zip", ["Downloads", "Projects/website"]),
    ]
    for name, folders in groups:
        payload = rng.randbytes(240_000)
        for folder in folders:
            target = DISK / folder / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(payload)


# ─────────────────────────────────────────────────────── the JSON-RPC client ──


class Rpc:
    """A newline-delimited JSON-RPC client for ``diskgoup serve``."""

    def __init__(self, process: subprocess.Popen[str]) -> None:
        self.process = process
        self.counter = 0

    def call(self, method: str, params: dict[str, object] | None = None) -> dict:
        self.counter += 1
        request = {"id": self.counter, "method": method, "params": params or {}}
        assert self.process.stdin is not None
        assert self.process.stdout is not None
        self.process.stdin.write(json.dumps(request) + "\n")
        self.process.stdin.flush()
        while True:
            line = self.process.stdout.readline()
            if not line:
                raise RuntimeError(f"{method}: the server closed the connection")
            message = json.loads(line)
            if message.get("id") != self.counter:
                # A notification (scan progress) — not our answer.
                continue
            if "error" in message:
                raise RuntimeError(f"{method}: {message['error'].get('message')}")
            return message["result"]


def scan(env: dict[str, str]) -> None:
    subprocess.run(
        ["uv", "run", "diskgoup", "scan", str(DISK)],
        cwd=REPO,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )


def collect(rpc: Rpc) -> dict[str, object]:
    scans = rpc.call("scans.list")["scans"]
    scan_id = scans[0]["scan_id"]
    reference = {"path": str(DISK), "scan_id": scan_id}

    tree = rpc.call("explore.tree", reference)["tree"]

    # Every directory of the tree, so the demo can open any folder.
    directories: list[str] = []

    def walk(node: dict) -> None:
        if node.get("is_dir"):
            directories.append(node["path"])
        for child in node.get("children") or []:
            walk(child)

    walk(tree)

    folders = {}
    for path in directories:
        result = rpc.call("explore.children", {**reference, "path": path})
        # The scan totals sit at the top level of the demo data — repeating
        # them in every folder would triple the file for nothing.
        folders[path] = {key: value for key, value in result.items() if key != "scan"}

    layouts = {
        view: rpc.call("view.layout", {**reference, "view": view, "depth": 3})["items"]
        for view in ("treemap", "sunburst", "flame", "bubbles", "mindmap")
    }

    return {
        "scan": rpc.call("scans.list")["scans"][0],
        "volumes": [],
        "root": str(DISK),
        "folders": folders,
        "sizes": rpc.call("explore.sizes", {**reference, "limit": 60})["entries"],
        "types": rpc.call("explore.types", reference)["types"],
        "age": rpc.call("explore.age", reference)["buckets"],
        "reclaimable": rpc.call("explore.reclaimable", reference),
        "layouts": layouts,
        "duplicates": rpc.call("duplicates.find", reference),
    }


def demo_volumes(scan: dict[str, object]) -> list[dict[str, object]]:
    """The volumes of the sample machine.

    The real ones are not used: they describe the disk this script happens
    to run on, not the disk the demo shows.
    """
    gib = 1024**3
    total = 494 * gib
    used = int(scan["total_size"]) + 26 * gib
    external_total = 1024 * gib
    external_used = 412 * gib
    return [
        {
            "device": "/dev/disk3s5",
            "mountpoint": "/Users",
            "label": "Macintosh HD",
            "fstype": "apfs",
            "total": total,
            "used": used,
            "free": total - used,
            "used_percent": round(used / total * 100, 1),
            "removable": False,
        },
        {
            "device": "/dev/disk4s1",
            "mountpoint": "/Volumes/Backup",
            "label": "Backup",
            "fstype": "exfat",
            "total": external_total,
            "used": external_used,
            "free": external_total - external_used,
            "used_percent": round(external_used / external_total * 100, 1),
            "removable": True,
        },
    ]


def realistic_scan(scan: dict[str, object]) -> dict[str, object]:
    """Give the scan the timings a real one would have."""
    duration = 12.4
    finished = float(scan["finished_at"])
    scan["duration"] = duration
    scan["started_at"] = finished - duration
    return scan


def rewrite(value: object) -> object:
    """Point every path at the shown home directory.

    macOS resolves ``/tmp`` to ``/private/tmp``, so both spellings of the
    sample disk have to be rewritten.
    """
    if isinstance(value, str):
        return value.replace(f"/private{DISK}", SHOWN_ROOT).replace(str(DISK), SHOWN_ROOT)
    if isinstance(value, list):
        return [rewrite(item) for item in value]
    if isinstance(value, dict):
        # The keys are paths too — the folder map is keyed by them.
        return {str(rewrite(key)): rewrite(item) for key, item in value.items()}
    return value


def fix_names(value: object) -> None:
    """Name every path after the rewritten one.

    The CLI names an entry after the last segment of its path. The root of the
    sample disk is a temp directory, so after the rewrite that name would
    still be the temp name — in the breadcrumbs, in the top-sizes table and
    in the charts.
    """
    if isinstance(value, dict):
        path = value.get("path")
        name = value.get("name")
        if isinstance(path, str) and isinstance(name, str) and name != "Safe to clean":
            value["name"] = Path(path).name or path
        for item in value.values():
            fix_names(item)
    elif isinstance(value, list):
        for item in value:
            fix_names(item)


def main() -> int:
    if not REPO.joinpath("pyproject.toml").exists():
        print("run this from the repository root", file=sys.stderr)
        return 1

    rng = random.Random(SEED)
    print(f"building the sample disk in {DISK} …")
    build_disk(rng)

    env = dict(os.environ)
    env["DISKGOUP_INDEX"] = str(INDEX)
    INDEX.parent.mkdir(parents=True, exist_ok=True)
    if INDEX.exists():
        INDEX.unlink()

    print("scanning …")
    scan(env)

    print("collecting the payloads …")
    process = subprocess.Popen(
        ["uv", "run", "diskgoup", "serve"],
        cwd=REPO,
        env=env,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        bufsize=1,
    )
    try:
        rpc = Rpc(process)
        data = collect(rpc)
    finally:
        process.terminate()
        process.wait(timeout=10)

    data["scan"] = realistic_scan(data["scan"])
    data["volumes"] = demo_volumes(data["scan"])

    OUT.parent.mkdir(parents=True, exist_ok=True)
    data = rewrite(data)
    fix_names(data)
    OUT.write_text(json.dumps(data, separators=(",", ":")) + "\n")
    size = OUT.stat().st_size / 1024
    print(f"wrote {OUT} ({size:.0f} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
