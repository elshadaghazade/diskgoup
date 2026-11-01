---
title: File kinds
description: The eleven file kinds DiskGOup classifies into, and the rules that decide them.
---

Every file and folder in a scan is put into one of **eleven kinds**. The
breakdown by kind is what the sidebar shows, what the type report is built
from, and what the snapshot comparison compares.

## The eleven kinds

| Kind | What lands in it |
|---|---|
| `game` | Game content — detected by the folder, not the extension. |
| `video` | `.mp4` `.mov` `.mkv` `.avi` `.webm` `.wmv` `.flv` `.m4v` `.mpg` `.mpeg` |
| `audio` | `.mp3` `.flac` `.wav` `.aac` `.ogg` `.m4a` `.alac` |
| `image` | `.png` `.jpg` `.jpeg` `.gif` `.webp` `.svg` `.bmp` `.tiff` `.heic` `.raw` `.psd` |
| `archive` | `.zip` `.7z` `.rar` `.tar` `.gz` `.bz2` `.xz` `.zst` `.iso` `.dmg` `.img` `.vhd` `.vhdx` |
| `document` | `.pdf` `.doc` `.docx` `.odt` `.rtf` `.txt` `.md` `.rst` `.csv` `.xls` `.xlsx` `.ods` `.ppt` `.pptx` `.key` `.numbers` `.pages` `.epub` `.mobi` |
| `code` | `.py` `.js` `.ts` `.tsx` `.jsx` `.go` `.rs` `.java` `.c` `.cpp` `.h` `.cs` `.rb` `.php` `.swift` `.kt` `.sh` `.json` `.yaml` `.yml` `.toml` `.xml` `.html` `.css` `.sql` `.db` `.sqlite` |
| `cache` | Cache, log and temporary content. |
| `application` | `.exe` `.msi` `.so` `.dylib` `.app` `.deb` `.rpm` `.pkg` `.appimage` |
| `system` | `.dll` `.sys` `.drv` `.efi` |
| `other` | Everything else — including every file with no extension. |

The order they are presented in is fixed: game → video → archive → document →
cache → application → audio → image → code → system → other.

## How a file is classified

The extension decides, unless a parent folder has already decided.

| Rule | Effect |
|---|---|
| The file has an extension in the table above | That kind. |
| The file has no extension, or an unknown one | `other`. |

The extension is read straight off the name rather than through
`pathlib.PurePath`, whose parser is pure Python and showed up as a
measurable part of the cost of a scan.

:::note
`.ts` is TypeScript here, not an MPEG transport stream. A developer machine
holds thousands of small `.ts` sources; broadcast captures in that format are
rare.
:::

## How a folder is classified

A folder's **name** decides, and the decision is inherited by everything
below it.

| Folder name matches | Kind |
|---|---|
| Contains `cache` anywhere | `cache` |
| Has `log` or `logs` as a whole word | `cache` |
| Has `temp` or `tmp` as a whole word | `cache` |
| Has `game`, `games`, `steam`, `epic`, `gog`, `origin`, `uplay` or `battle.net` as a whole word | `game` |
| Has `app`, `apps`, `application`, `applications`, `program`, `programs`, `software` or `bin` as a whole word | `application` |
| Anything else | `other` |

The matching is deliberately asymmetric:

- **`cache` matches anywhere.** `Cache`, `AppCache` and `cached_content` all
  match.
- **`log`, `logs`, `temp` and `tmp` must be whole words.** Matching `log`
  anywhere would catch `Dialog` and `Catalogue`; matching `temp` anywhere
  would catch `Template`. A word boundary is any of a space, a dot, an
  underscore or a dash.

## Inheritance

Once a folder is classified, its **whole subtree** inherits that kind. A
`Cache` folder contains caches, whatever the extensions of the files inside
it are. A `Steam` folder is game content, whatever is in it.

The inheritance means the numbers add up: a file is counted in exactly one
kind, so the type report's total equals the size of the scan.

:::caution
This is why the kind of a folder is decided by its **name**, not by what it
contains. A folder called `logs` holding your only copy of something is
still reported as cache, and the reclaimable list will offer it. Move it out
of the folder, or do not stage it — the cleanup gate always asks before
anything is removed.
:::

## Where the kinds are used

| Place | What it uses the kind for |
|---|---|
| `diskgoup types` | The file-type breakdown. |
| `diskgoup reports types` | The CSV type report. |
| `diskgoup snapshots compare` | Which category grew. |
| `diskgoup search --kind` | Filtering the search. |
| The treemap colours | The colour of a folder. |
| `diskgoup cleanup` | The reclaimable list — only `cache` folders are offered. |

## Reclaimable kinds

Only **`cache`** is reclaimable. The
[reclaimable list](/guide/cleanup/#safe-to-clean) is built from the top-most
cache folders — the ones whose parent is not itself a cache folder — so
staging one covers its whole subtree and nothing is offered twice.

Every other kind is there to be *measured*, not deleted.
