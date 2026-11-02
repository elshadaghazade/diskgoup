#!/usr/bin/env python3
"""Move the built installer to a fixed name.

The download links in the documentation are stable — they point at
`releases/latest/download/<name>` — so the assets have to carry a fixed name
instead of the version electron-builder puts in them.

    python3 scripts/pick-artifact.py "electron/release/DiskGOup-*-arm64.dmg" \\
        "DiskGOup-macOS-arm64.dmg"

The first file matching the pattern is moved into `release-assets/`. It fails
when the pattern matches nothing, or more than one file, so a build that
produced the wrong artifact is caught instead of shipped.

Only the standard library is needed.
"""

from __future__ import annotations

import glob
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "release-assets"


def main() -> int:
    if len(sys.argv) != 3:
        print(__doc__, file=sys.stderr)
        return 2
    pattern, name = sys.argv[1], sys.argv[2]

    matches = sorted(glob.glob(pattern, recursive=True))
    if not matches:
        print(f"✗ nothing matches {pattern}", file=sys.stderr)
        return 1
    if len(matches) > 1:
        print(f"✗ {pattern} matches {len(matches)} files:", file=sys.stderr)
        for match in matches:
            print(f"    {match}", file=sys.stderr)
        return 1

    OUT.mkdir(exist_ok=True)
    target = OUT / name
    shutil.move(matches[0], target)
    print(f"✓ {matches[0]} → {target.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
