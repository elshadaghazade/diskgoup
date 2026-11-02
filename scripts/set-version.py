#!/usr/bin/env python3
"""Write the release version into the project files.

The tag is the single source of truth for a release: `v0.2.0` means the
version `0.2.0`, and it has to reach the places that carry it — the Python
package, both `package.json` files and therefore the installer names.

    python3 scripts/set-version.py 0.2.0

Only the standard library is needed.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# The files that carry the version, and how to find the line to rewrite.
PY_VERSION = re.compile(r'__version__\s*=\s*"[^"]*"')
TOML_VERSION = re.compile(r'^version\s*=\s*"[^"]*"', re.MULTILINE)
# The top-level "version" key of a package.json — two spaces of indentation.
JSON_VERSION = re.compile(r'^  "version": "[^"]*",$', re.MULTILINE)


def main() -> int:
    # The console on Windows is cp1252 and cannot hold a "✓".
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    if len(sys.argv) != 2:
        print(__doc__, file=sys.stderr)
        return 2
    version = sys.argv[1].strip().lstrip("vV")
    if not re.fullmatch(r"\d+\.\d+\.\d+([-+.][\w.]+)?", version):
        print(f"✗ {version!r} is not a version like 1.2.3", file=sys.stderr)
        return 2

    targets = [
        (ROOT / "src" / "diskgoup" / "__init__.py", PY_VERSION, f'__version__ = "{version}"'),
        (ROOT / "pyproject.toml", TOML_VERSION, f'version = "{version}"'),
        (ROOT / "electron" / "package.json", JSON_VERSION, f'  "version": "{version}",'),
        (ROOT / "ui" / "package.json", JSON_VERSION, f'  "version": "{version}",'),
    ]
    for path, pattern, replacement in targets:
        if not path.exists():
            print(f"✗ {path} is missing", file=sys.stderr)
            return 1
        text = path.read_text(encoding="utf-8")
        new, count = pattern.subn(replacement, text, count=1)
        if count == 0:
            print(f"✗ no version found in {path}", file=sys.stderr)
            return 1
        path.write_text(new, encoding="utf-8")
        print(f"✓ {path.relative_to(ROOT)} → {version}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
