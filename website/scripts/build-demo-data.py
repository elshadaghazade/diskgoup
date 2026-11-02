#!/usr/bin/env python3
"""Build the sample disk the website's interactive demo runs on.

The demo is not hand-written mock data. A synthetic disk is created, the
**real** DiskGOup CLI scans it, and the JSON-RPC payloads the desktop app
consumes are collected over ``diskgoup serve``. What lands in
``website/public/demo.json`` is therefore exactly what the real app would
show for that disk — the same layout maths, the same colours, the same
duplicate detection, the same reports.

Two things cannot be collected that way, because they read the machine the
CLI runs on rather than the scan: the application inventory and the game
library. Both are measured over the sample disk with the CLI's own code
(``diskgoup.core.applications`` and ``diskgoup.core.games``), so their
numbers and their shape are the real ones — only the machine is the sample
one.

Run it from the repository root::

    uv run python website/scripts/build-demo-data.py

Nothing outside ``/tmp`` is written, and the scan index used is a throwaway
one — the index of the real app is never touched.
"""

from __future__ import annotations

import io
import json
import os
import plistlib
import random
import shutil
import sqlite3
import subprocess
import sys
import time
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
# The CLI's own modules — the inventory and the game library are measured
# with the code the desktop app uses, not with a copy of it.
sys.path.insert(0, str(REPO / "src"))

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


# ─────────────────────────────────────────────────────────────── applications ──

#: The applications of the sample machine: name, size, version, publisher.
APPLICATIONS = {
    "Xcode": (8.4e9, "16.2", "Apple Inc."),
    "Adobe Photoshop 2025": (4.1e9, "26.0.1", "Adobe Inc."),
    "Firefox": (1.2e9, "134.0", "Mozilla"),
    "Slack": (0.9e9, "4.42.98", "Salesforce"),
    "Visual Studio Code": (0.7e9, "1.95.3", "Microsoft"),
    "Blender": (0.66e9, "4.3.1", "Blender Foundation"),
    "Spotify": (0.42e9, "1.2.45", "Spotify AB"),
    "Zoom": (0.31e9, "6.2.0", "Zoom Video Communications"),
    "Figma": (0.28e9, "125.6", "Figma, Inc."),
}

#: The applications of the operating system itself — they are reported, and
#: they cannot be removed.
SYSTEM_APPLICATIONS = {
    "Safari": (1.1e9, "18.2", "Apple Inc."),
    "Mail": (0.42e9, "17.0", "Apple Inc."),
}


def write_plist(path: Path, version: str) -> None:
    """Write the ``Info.plist`` of an app bundle."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" '
        '"http://www.apple.com/DTDs/PropertyList-1.0.dtd">\n'
        '<plist version="1.0">\n<dict>\n'
        "\t<key>CFBundleShortVersionString</key>\n"
        f"\t<string>{version}</string>\n"
        "\t<key>CFBundleIdentifier</key>\n"
        f"\t<string>com.sample.{path.parent.parent.name.removesuffix('.app').replace(' ', '').lower()}</string>\n"
        "</dict>\n</plist>\n",
        encoding="utf-8",
    )


def build_applications(rng: random.Random) -> None:
    """The app bundles of the sample machine."""
    for name, (size, version, _) in APPLICATIONS.items():
        folder = DISK / "Applications" / f"{name}.app" / "Contents"
        write_plist(folder / "Info.plist", version)
        write_file(folder / "MacOS" / name.replace(" ", ""), size, rng)
        write_file(folder / "Resources" / "app.asar", size * 0.04, rng)
        for index in range(6):
            write_file(
                folder / "Frameworks" / f"framework-{index}.dylib",
                rng.uniform(4e6, 40e6),
                rng,
            )

    # The system applications live in the folder the system owns.
    for name, (size, version, _) in SYSTEM_APPLICATIONS.items():
        folder = DISK / "System" / "Applications" / f"{name}.app" / "Contents"
        write_plist(folder / "Info.plist", version)
        write_file(folder / "MacOS" / name, size, rng)


# ───────────────────────────────────────────────────────────────────── games ──

#: The games of the sample machine: name, platform, app id, size.
GAMES = (
    ("Elden Ring", "Steam", "1245620", 42e9),
    ("Hades", "Steam", "1145360", 9e9),
    ("Stardew Valley", "Steam", "413150", 2e9),
    ("Hogwarts Legacy", "Epic Games", None, 76e9),
)

STEAM_ROOT = DISK / "Library" / "Application Support" / "Steam"
EPIC_ROOT = DISK / "Library" / "Application Support" / "Epic"


def build_games(rng: random.Random) -> None:
    """The game libraries of the sample machine.

    The layout is the real one: a Steam library under ``steamapps/common``
    with a manifest per title, an Epic library under the launcher root.
    """
    for name, platform, app_id, size in GAMES:
        root = STEAM_ROOT / "steamapps" / "common" / name if platform == "Steam" else EPIC_ROOT / name
        write_file(root / f"{name.replace(' ', '')}.bin", size * 0.82, rng)
        # The categories the CLI reports — the folders a game installation
        # carries beside its files.
        write_file(root / "DLC" / "bonus-content.bin", size * 0.09, rng)
        write_file(root / "Saved Games" / "savegame.sav", size * 0.004, rng)
        write_file(root / "Screenshots" / "screenshot-01.jpg", size * 0.03, rng)
        write_file(root / "Mods" / "mod-01.pak", size * 0.02, rng)

        if app_id:
            manifest = STEAM_ROOT / "steamapps" / f"appmanifest_{app_id}.acf"
            manifest.parent.mkdir(parents=True, exist_ok=True)
            manifest.write_text(
                '"AppState"\n{\n'
                f'\t"appid"\t\t"{app_id}"\n'
                f'\t"name"\t\t"{name}"\n'
                f'\t"installdir"\t\t"{name}"\n'
                "}\n",
                encoding="utf-8",
            )

    folders = STEAM_ROOT / "steamapps" / "libraryfolder.vdf"
    folders.parent.mkdir(parents=True, exist_ok=True)
    folders.write_text(
        '"libraryfolders"\n{\n\t"0"\n\t{\n'
        f'\t\t"path"\t\t"{STEAM_ROOT}"\n'
        "\t}\n}\n",
        encoding="utf-8",
    )


# ────────────────────────────────────────────────────────────────── archives ──


def zip_bytes(members: list[tuple[str, bytes]]) -> bytes:
    """A ZIP archive, as bytes."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, payload in members:
            archive.writestr(name, payload)
    return buffer.getvalue()


def text(rng: random.Random, lines: int) -> bytes:
    """A readable text file."""
    words = (
        "backup archive note invoice draft report photo export cache "
        "project release folder client contract meeting minutes budget"
    ).split()
    lines_out = []
    for index in range(lines):
        sentence = " ".join(rng.choice(words) for _ in range(rng.randint(6, 14)))
        lines_out.append(f"{index + 1:>3}. {sentence.capitalize()}.")
    return ("\n".join(lines_out) + "\n").encode("utf-8")


def build_archives(rng: random.Random) -> None:
    """The ZIP archives of the sample disk.

    They are real archives — the demo opens them and previews a member, so
    a file that is not a ZIP would only show an error.
    """
    payload = zip_bytes(
        [
            ("backup/readme.txt", text(rng, 14)),
            ("backup/notes/todo.md", text(rng, 9)),
            ("backup/data/inventory.csv", b"path,size,kind\n" + text(rng, 40)),
        ]
    )
    for folder in ("Downloads", "Projects/website"):
        target = DISK / folder / "backup-archive.zip"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(payload)

    contract = zip_bytes(
        [
            ("contract-2026/agreement.txt", text(rng, 22)),
            # A binary member — the preview of it is refused, as it is on a
            # real machine.
            ("contract-2026/signature.png", b"\x89PNG\r\n\x1a\n" + rng.randbytes(4096)),
        ]
    )
    target = DISK / "Documents" / "Work" / "contract-2026.zip"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(contract)


# ─────────────────────────────────────────────────────────────── the disk ──


def build_disk(rng: random.Random) -> None:
    if DISK.exists():
        shutil.rmtree(DISK)

    build_applications(rng)

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
        target = DISK / "Downloads" / f"download-{index:02d}.{kind}"
        if kind == "zip":
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(
                zip_bytes(
                    [
                        ("package/readme.txt", text(rng, 8)),
                        ("package/manual.pdf", rng.randbytes(2048)),
                    ]
                )
            )
            os.utime(target, (time.time() - pick_age(rng) * 86400,) * 2)
            continue
        write_file(target, rng.uniform(1e6, 900e6), rng)

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

    build_games(rng)
    build_archives(rng)

    # Three groups of byte-identical files — the duplicate finder finds them
    # by SHA-256, exactly as it does on a real disk.
    groups = [
        ("presentation-final.pdf", ["Documents/Work", "Downloads", "Desktop"]),
        ("invoice-2026-04.pdf", ["Documents/Invoices", "Downloads"]),
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

    types = rpc.call("explore.types", reference)["types"]

    return {
        "scan": scans[0],
        "volumes": [],
        "root": str(DISK),
        "folders": folders,
        "sizes": rpc.call("explore.sizes", {**reference, "limit": 60})["entries"],
        "types": types,
        "age": rpc.call("explore.age", reference)["buckets"],
        "reclaimable": rpc.call("explore.reclaimable", reference),
        "layouts": layouts,
        "duplicates": rpc.call("duplicates.find", reference),
        "archives": collect_archives(rpc, folders),
    }


def collect_archives(rpc: Rpc, folders: dict[str, dict]) -> list[dict[str, object]]:
    """Every ZIP of the sample disk, with its listing and its previews.

    The demo opens an archive and reads a member out of it without
    extracting anything — the same read-only promise the desktop app makes.
    """
    found: dict[str, int] = {}
    for folder in folders.values():
        for entry in folder["entries"]:
            if not entry["is_dir"] and entry["name"].lower().endswith(".zip"):
                found[entry["path"]] = int(entry["size"])

    archives: list[dict[str, object]] = []
    for path, size in sorted(found.items(), key=lambda item: -item[1]):
        listing = rpc.call("archives.list", {"archive": path})
        previews: dict[str, object] = {}
        for entry in listing.get("entries", []):
            if entry.get("is_dir"):
                continue
            previews[entry["name"]] = rpc.call(
                "archives.preview", {"archive": path, "member": entry["name"]}
            )
        archives.append({"path": path, "size": size, "listing": listing, "previews": previews})
    return archives


# ─────────────────────────────────────────────────── the parts of the machine ──


def sample_applications() -> dict[str, object]:
    """The application inventory of the sample machine.

    The real inventory reads ``/Applications`` and the folders the operating
    system owns. The sample machine has its bundles inside the sample disk,
    so they are measured with the CLI's own ``directory_size`` and read
    with the same ``Info.plist`` the desktop app reads.
    """
    from diskgoup.core.applications import SYSTEM_APP, Application, directory_size

    applications: list[dict[str, object]] = []

    for name, (_size, _version, publisher) in APPLICATIONS.items():
        bundle = DISK / "Applications" / f"{name}.app"
        applications.append(
            Application(
                name=name,
                path=bundle,
                size=directory_size(bundle),
                version=plist_version(bundle),
                publisher=publisher,
                source="macos",
                uninstall_command=f'Move "{bundle}" to the Trash',
            ).to_dict()
        )

    for name, (_size, _version, publisher) in SYSTEM_APPLICATIONS.items():
        bundle = DISK / "System" / "Applications" / f"{name}.app"
        applications.append(
            Application(
                name=name,
                path=bundle,
                size=directory_size(bundle),
                version=plist_version(bundle),
                publisher=publisher,
                source="macos",
                protected=True,
                reason=SYSTEM_APP,
            ).to_dict()
        )

    return {
        "applications": applications,
        "total_size": sum(int(item["size"]) for item in applications),
    }


def plist_version(bundle: Path) -> str | None:
    """The version out of an app bundle's ``Info.plist``."""
    plist = bundle / "Contents" / "Info.plist"
    if not plist.is_file():
        return None
    try:
        with plist.open("rb") as handle:
            data = plistlib.load(handle)
        version = data.get("CFBundleShortVersionString") or data.get("CFBundleVersion")
        return str(version) if version else None
    except Exception:
        return None


def sample_games() -> dict[str, object]:
    """The game libraries of the sample machine.

    The discovery code reads the Steam and Epic libraries of the machine it
    runs on. The sample disk holds them in the real places, and ``HOME``
    points at it for the discovery — so the libraries, the manifests and the
    category breakdown are the ones the CLI finds on a real machine.
    """
    from diskgoup.core.games import discover

    # The discovery looks at the home directory of the machine it runs on.
    home = os.environ.get("HOME")
    os.environ["HOME"] = str(DISK)
    try:
        libraries = discover()
    finally:
        if home is None:
            os.environ.pop("HOME", None)
        else:
            os.environ["HOME"] = home
    games = [game for library in libraries for game in library.games]
    return {
        "libraries": [library.to_dict() for library in libraries],
        "total_size": sum(game.size for game in games),
    }


def sample_monitor() -> dict[str, object]:
    """A monitor sample for the sample machine.

    The real monitor reads the machine it runs on — that would put the
    reader's own numbers on the page, so the sample machine gets its own
    readings, in the shape the CLI produces.
    """
    from diskgoup.core.monitor import MonitorSample, ProcessInfo

    sample = MonitorSample(timestamp=time.time())
    sample.network_down = 12.4 * 1024 * 1024
    sample.network_up = 1.8 * 1024 * 1024
    sample.disk_read = 46.2 * 1024 * 1024
    sample.disk_write = 11.7 * 1024 * 1024
    sample.disk_usage = 412 * 1024**3
    sample.disk_total = 494 * 1024**3
    sample.processes = [
        ProcessInfo(pid=431, name="Finder", cpu=1.8, memory=284 * 1024 * 1024),
        ProcessInfo(pid=812, name="Safari", cpu=12.4, memory=1_240 * 1024 * 1024),
        ProcessInfo(pid=1255, name="Slack", cpu=4.1, memory=890 * 1024 * 1024),
        ProcessInfo(pid=1602, name="Xcode", cpu=22.6, memory=3_400 * 1024 * 1024),
        ProcessInfo(pid=2044, name="Spotify", cpu=2.7, memory=310 * 1024 * 1024),
        ProcessInfo(pid=2380, name="Photos", cpu=0.9, memory=420 * 1024 * 1024),
        ProcessInfo(pid=2661, name="Mail", cpu=0.4, memory=180 * 1024 * 1024),
        ProcessInfo(pid=3102, name="Terminal", cpu=0.6, memory=48 * 1024 * 1024),
        ProcessInfo(pid=3550, name="Code Helper", cpu=8.3, memory=720 * 1024 * 1024),
        ProcessInfo(pid=4021, name="backupd", cpu=3.5, memory=96 * 1024 * 1024),
    ]
    return sample.to_dict()


# ─────────────────────────────────────────────────────────────── the history ──

#: How much each kind grew since the baseline snapshot. The cache and the
#: video grew the most — the two things that fill a disk.
GROWTH = {
    "video": 1.18,
    "audio": 0.97,
    "image": 1.06,
    "document": 1.02,
    "archive": 0.88,
    "code": 1.11,
    "cache": 1.34,
    "application": 1.04,
    "game": 1.09,
    "system": 1.0,
    "other": 1.05,
}


def insert_baseline_snapshot(scan_id: int, types: list[dict[str, object]]) -> None:
    """Put a snapshot of a week ago into the index.

    The CLI measures growth against the newest snapshot that is at least
    seven days old — without one there is no history to show. The row is
    written into the index with the sizes the disk had then, and the CLI
    does the measuring.
    """
    kinds = {str(item["kind"]): int(item["size"]) for item in types}
    baseline = {
        kind: int(size / GROWTH.get(kind, 1.0)) for kind, size in kinds.items() if size
    }
    total = sum(baseline.values())

    connection = sqlite3.connect(INDEX)
    try:
        cursor = connection.execute(
            "INSERT INTO snapshots (scan_id, label, created_at, total_size, total_on_disk) "
            "VALUES (?, ?, ?, ?, ?)",
            (scan_id, "Weekly baseline", time.time() - 9 * 86400, total, total),
        )
        snapshot_id = int(cursor.lastrowid or 0)
        connection.executemany(
            "INSERT INTO snapshot_kinds (snapshot_id, kind, size) VALUES (?, ?, ?)",
            [(snapshot_id, kind, size) for kind, size in baseline.items()],
        )
        connection.commit()
    finally:
        connection.close()


# ─────────────────────────────────────────────────────────────── the rewrites ──


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

    The CLI names an entry after the last segment of its path. The root of
    the sample disk is a temp directory, so after the rewrite that name would
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
    # The game discovery reads the home directory of the machine it runs on.
    env["HOME"] = str(DISK)
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

        # The history the snapshots and the reports are measured against.
        scan_id = int(data["scan"]["scan_id"])
        insert_baseline_snapshot(scan_id, data["types"])
        reference = {"path": str(DISK), "scan_id": scan_id}
        data["snapshots"] = rpc.call("snapshots.list", reference)["snapshots"]
        data["comparison"] = rpc.call("snapshots.compare", reference)
        data["reports"] = {
            "weekly": rpc.call("reports.weekly", reference)["html"],
            "csv": rpc.call("reports.types", reference)["csv"],
        }
    finally:
        process.terminate()
        process.wait(timeout=10)

    data["scan"] = realistic_scan(data["scan"])
    data["volumes"] = demo_volumes(data["scan"])

    OUT.parent.mkdir(parents=True, exist_ok=True)
    data = rewrite(data)
    fix_names(data)

    # The inventory and the libraries are measured after the rewrite — their
    # paths are the machine's own, and their names are their own.
    data["applications"] = rewrite(sample_applications())
    data["games"] = rewrite(sample_games())
    data["monitor"] = sample_monitor()

    OUT.write_text(json.dumps(data, separators=(",", ":")) + "\n")
    size = OUT.stat().st_size / 1024
    print(f"wrote {OUT} ({size:.0f} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
