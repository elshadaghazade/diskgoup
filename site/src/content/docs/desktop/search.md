---
title: Search
description: Find files by name, path, type, date and size — every condition applies together.
---

![The Search section](/app/12-search.png)

Search asks the index a question and lists what it finds. Every condition
applies **together** — a file has to match all of them.

| Condition | What it accepts |
|---|---|
| **Name** | A fragment of the name. `archive`, `.mp4`, `Work` |
| **In path** | A fragment of the full path. |
| **Extensions** | A comma-separated list. `mp4, zip` |
| **Entry type** | Any, files only, folders only. |
| **From date** / **To date** | The day the file was last modified. Both ends are inclusive. |
| **Minimum size** / **Maximum size** | `100MB`, `2GB`, `500KB`. Both ends are inclusive. |

The result is a table of the matches with their path and size, and the page
controls when there is more than one page. The header says how many matches
there are in the whole scan, not only on the page.

The search reads the index of the open scan — it does not walk the disk. See
[Searching](/guide/search/) for the command-line equivalent.
