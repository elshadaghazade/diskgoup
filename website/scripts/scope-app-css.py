#!/usr/bin/env python3
"""Scope the desktop app's stylesheet for the website.

The app in ``ui/src/styles.css`` styles ``body`` and ``:root`` — it assumes
it owns the whole window. On the website it shares the page with a landing
site, so every rule is rewritten to live under ``.dg-app`` instead.

Run it from the repository root::

    python3 website/scripts/scope-app-css.py

The result is committed, so the website builds without this step.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SOURCE = REPO / "ui" / "src" / "styles.css"
TARGET = REPO / "website" / "app" / "demo.css"

SCOPE = ".dg-app"

COMMENT = re.compile(r"/\*.*?\*/", re.S)


def strip_comments(text: str) -> str:
    return COMMENT.sub("", text)


def scope_selector(selector: str) -> str:
    """Put one selector list under the demo scope."""
    scoped = []
    for part in (piece.strip() for piece in selector.split(",")):
        if not part:
            continue
        if part == ":root":
            scoped.append(SCOPE)
        elif part == "*":
            scoped.append(f"{SCOPE} *")
        elif part in ("html", "body", "#root"):
            scoped.append(SCOPE)
        else:
            scoped.append(f"{SCOPE} {part}")
    return ", ".join(scoped)


def parse(css: str) -> list[tuple[str, str]]:
    """Split a stylesheet into its rules: the text before ``{`` and the body."""
    rules: list[tuple[str, str]] = []
    index = 0
    length = len(css)
    while index < length:
        # The next opening brace, skipping the comments.
        brace = -1
        cursor = index
        while cursor < length:
            if css.startswith("/*", cursor):
                cursor = css.find("*/", cursor) + 2
                continue
            if css[cursor] == "{":
                brace = cursor
                break
            cursor += 1
        if brace == -1:
            break

        # Its matching closing brace.
        depth = 0
        end = brace
        while end < length:
            if css.startswith("/*", end):
                end = css.find("*/", end) + 2
                continue
            if css[end] == "{":
                depth += 1
            elif css[end] == "}":
                depth -= 1
                if depth == 0:
                    break
            end += 1

        rules.append((css[index:brace], css[brace + 1 : end]))
        index = end + 1
    return rules


def replace_selector(prelude: str, scoped: str) -> str:
    """Swap the selector of a rule, keeping its comments and its spacing."""
    stripped = prelude.rstrip()
    trailing = prelude[len(stripped) :]
    comment_end = stripped.rfind("*/")
    if comment_end == -1:
        head, rest = "", stripped
    else:
        head, rest = stripped[: comment_end + 2], stripped[comment_end + 2 :]
    gap = len(rest) - len(rest.lstrip())
    return f"{head}{rest[:gap]}{scoped}{trailing}"


def transform(css: str) -> str:
    """Rewrite every rule of a stylesheet so it lives under the scope."""
    out: list[str] = []
    for prelude, body in parse(css):
        selector = strip_comments(prelude).strip()
        if selector.startswith("@keyframes") or selector.startswith("@font-face"):
            # The selectors inside a keyframe block are percentages.
            out.append(f"{prelude}{{{body}}}")
        elif selector.startswith("@media") or selector.startswith("@supports"):
            out.append(f"{prelude}{{{transform(body)}}}")
        else:
            out.append(f"{replace_selector(prelude, scope_selector(selector))}{{{body}}}")
    return "".join(out)


def main() -> int:
    css = SOURCE.read_text()
    header = (
        "/* The desktop app's own stylesheet, scoped for the website.\n"
        " *\n"
        " * Generated from ui/src/styles.css by website/scripts/scope-app-css.py —\n"
        " * every rule now lives under .dg-app, so the demo cannot reach the\n"
        " * landing page around it. Edit the app's stylesheet, then run the script.\n"
        " */\n\n"
    )
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    TARGET.write_text(header + transform(css))
    print(f"wrote {TARGET} ({TARGET.stat().st_size / 1024:.0f} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
