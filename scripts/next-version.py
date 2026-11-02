#!/usr/bin/env python3
"""Work out the version of the next release.

    python3 scripts/next-version.py             # the automatic choice
    python3 scripts/next-version.py --bump minor # force the level
    python3 scripts/next-version.py 0.3.0       # an explicit version

The rules:

* Before the first release there is no tag, so the version declared in
  `pyproject.toml` is the version to publish.
* After that the base is the higher of the declared version and the newest
  release tag, and the bump follows what was merged: a `feat:` commit means a
  minor release, a breaking change a major one, anything else a patch.

The release workflow calls this without arguments; the version it prints is
the one that is written into the project, tagged and published.

Only the standard library is needed.
"""

from __future__ import annotations

import re
import subprocess
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

VERSION_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")
# `feat:`, `feat(scope):` and `feat!:` — the conventional-commit feature marker.
FEATURE_RE = re.compile(r"^feat(\([^)]*\))?!?:", re.IGNORECASE)
BREAKING_RE = re.compile(r"BREAKING[ -]CHANGE")


def git(*args: str) -> str:
    """Run a git command and return its output (empty when it fails)."""
    result = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=False)
    return result.stdout if result.returncode == 0 else ""


def parse(version: str) -> tuple[int, int, int]:
    match = VERSION_RE.match(version)
    if not match:
        raise ValueError(f"{version!r} is not a version like 1.2.3")
    return int(match[1]), int(match[2]), int(match[3])


def declared_version() -> str:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    return str(pyproject["project"]["version"])


def newest_tag() -> str | None:
    """The newest release tag, with its `v` — `v0.2.0`, say."""
    tags = [tag for tag in git("tag", "--list", "v[0-9]*").split() if VERSION_RE.match(tag[1:])]
    if not tags:
        return None
    return max(tags, key=lambda tag: parse(tag[1:]))


def automatic_level(tag: str | None) -> str:
    """minor for a feature, major for a breaking change, patch otherwise."""
    if tag:
        subjects = git("log", "--format=%s", f"{tag}..HEAD").splitlines()
    else:
        subjects = git("log", "--format=%s").splitlines()
    if any(BREAKING_RE.search(subject) for subject in subjects):
        return "major"
    if any(FEATURE_RE.match(subject) for subject in subjects):
        return "minor"
    return "patch"


def bump(version: str, level: str) -> str:
    major, minor, patch = parse(version)
    if level == "major":
        return f"{major + 1}.0.0"
    if level == "minor":
        return f"{major}.{minor + 1}.0"
    return f"{major}.{minor}.{patch + 1}"


def main() -> int:
    args = sys.argv[1:]
    level = "auto"
    explicit: str | None = None

    if args:
        if args[0] == "--bump":
            if len(args) != 2:
                print(__doc__, file=sys.stderr)
                return 2
            level = args[1]
            if level not in {"auto", "patch", "minor", "major"}:
                print(f"✗ {level!r} is not auto, patch, minor or major", file=sys.stderr)
                return 2
        else:
            explicit = args[0]

    if explicit is not None:
        version = explicit.strip().lstrip("vV")
        try:
            parse(version)
        except ValueError as error:
            print(f"✗ {error}", file=sys.stderr)
            return 2
        print(version)
        return 0

    declared = declared_version()
    tag = newest_tag()
    if tag is None and level == "auto":
        # The first release publishes the version the project declares.
        version = declared
    else:
        base = max(declared, tag[1:], key=parse) if tag else declared
        chosen = level if level != "auto" else automatic_level(tag)
        version = bump(base, chosen)

    print(version)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
