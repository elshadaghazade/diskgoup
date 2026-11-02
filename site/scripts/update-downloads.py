#!/usr/bin/env python3
"""Point the documentation at a new release.

The download links themselves are stable — `releases/latest/download/…`
always serves the newest build — but the page names the version it was
written for and links to that release's notes. Run this after a release is
published:

    python3 site/scripts/update-downloads.py --version 0.2.0

The release workflow does it automatically, as part of the release commit, so a
release and the documentation never drift apart.

Only the standard library is needed.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PAGE = ROOT / "src" / "content" / "docs" / "getting-started" / "downloads.md"

REPO = "https://github.com/elshadaghazade/diskgoup"

START = "<!-- release:start -->"
END = "<!-- release:end -->"


def main() -> int:
    # The console on Windows is cp1252 and cannot hold a "✓".
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", required=True, help="the version, e.g. 0.2.0")
    args = parser.parse_args()

    version = args.version.strip().lstrip("vV")
    if not re.fullmatch(r"\d+\.\d+\.\d+([-+.][\w.]+)?", version):
        print(f"✗ {version!r} is not a version like 1.2.3", file=sys.stderr)
        return 2

    if not PAGE.exists():
        print(f"✗ {PAGE} is missing", file=sys.stderr)
        return 1

    text = PAGE.read_text(encoding="utf-8")
    if START not in text or END not in text:
        print(f"✗ {PAGE} has no {START} … {END} block", file=sys.stderr)
        return 1

    block = (
        f"{START}\n"
        f"**Latest release: `v{version}`** · "
        f"[the release notes →]({REPO}/releases/tag/v{version})\n"
        f"{END}"
    )
    new = re.sub(
        re.escape(START) + r".*?" + re.escape(END),
        lambda _: block,
        text,
        count=1,
        flags=re.DOTALL,
    )
    if new == text:
        print(f"the documentation already points at v{version}")
        return 0

    PAGE.write_text(new, encoding="utf-8")
    print(f"✓ downloads.md → v{version}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
