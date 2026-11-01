---
title: Cleaning up safely
description: The staged review flow — stage, review, validate, confirm, revalidate, recycle bin.
---

A disk analyser that deletes without asking is worse than useless. DiskGOup
never deletes anything straight away. Everything goes through a review list and
a series of checks.

```
stage → review → validate → confirm → revalidate → recycle bin
```

## The contract

| Step | What happens |
|---|---|
| **Stage** | Items are added to a review list. Protected and critical paths are **refused with a reason** — never silently ignored. |
| **Review** | The list is inspected. Items can be taken back off it at any time. |
| **Validate** | Every item is checked: does it still exist, is it still eligible, has it changed? |
| **Confirm** | The user approves. The CLI prints what is about to happen and asks. |
| **Revalidate** | The list is validated **again**, immediately before anything moves. |
| **Recycle bin** | The items are moved to the platform's trash. |

Cancelling at any point leaves every file exactly where it was.

## Staging

```bash
diskgoup cleanup stage ~/Downloads/archive.zip ~/Downloads/old-project
```

```
✔ staged 2 item(s)
refused /System/Volumes/Data/Library: System folders cannot be cleaned.
Nothing has been removed. Review the list, then commit.
```

A path that a protection rule covers is refused with the sentence the user
reads. Nothing was staged and nothing was removed.

Staging is **not** deletion — it only writes a row in the review list.

## Reviewing

```bash
diskgoup cleanup list
```

```
╭────────────────────────────────────────────────────────┬──────────┬─────────╮
│ Path                                                   │ Kind     │    Size │
├────────────────────────────────────────────────────────┼──────────┼─────────┤
│ /Users/you/Downloads/archive.zip                       │ archive  │ 812 MB  │
│ /Users/you/Downloads/old-project                       │ other    │  4.1 GB │
├────────────────────────────────────────────────────────┼──────────┼─────────┤
│ Total                                                  │          │ 4.9 GB  │
╰────────────────────────────────────────────────────────┴──────────┴─────────╯
```

To take something back off the list:

```bash
diskgoup cleanup remove ~/Downloads/old-project
diskgoup cleanup clear        # empty the whole list
```

## Validating

```bash
diskgoup cleanup validate
```

```
3 item(s) ready
issue /Users/you/Downloads/gone.mp4: File no longer exists.
issue /Users/you/Downloads/movie.mkv: File changed since the scan; re-scan to refresh.
```

Three things are checked:

1. **Does it still exist?** A file that has disappeared is reported, not
   attempted.
2. **Is it still eligible?** An item that has become protected since it was
   staged is refused with the reason.
3. **Has it changed?** A *file* whose size no longer matches what the scan
   recorded was modified after the scan — the decision was made on stale data.
   A *folder* that changed is fine: the whole subtree goes away anyway, and a
   cache folder is written to all the time.

## Committing

```bash
diskgoup cleanup commit
```

```
12 item(s) · 4.9 GB
  /Users/you/Downloads/archive.zip
  /Users/you/Downloads/old-project
  … and 10 more
Approve this cleanup? [y/N]:
```

```
✔ moved 12 item(s) to the recycle bin — the space comes back when the trash is emptied
```

`--yes` skips the prompt (useful in scripts). `--permanent` deletes for good
instead of using the trash.

:::caution
The recycle bin still holds the bytes until it is emptied. **Only a permanent
delete actually frees the space.** The default is the recycle bin because it is
recoverable; `--permanent` is the deliberate, irreversible choice.
:::

## The trash

Items go to the platform's recycle bin through
[`send2trash`](https://pypi.org/project/Send2Trash/):

| Platform | Trash |
|---|---|
| macOS | Trash |
| Windows | Recycle Bin |
| Linux | freedesktop trash |

A read-only file is handled the way a file manager handles it: the mark is
cleared and the removal is retried. A folder of read-only files fails as a
whole on Windows, so each entry is retried individually.

## What the index does afterwards

When an item is removed, its rows — and the rows of everything below it —
are deleted from the index, and the rolled-up totals of the folders that held
it are corrected. The index keeps telling the truth about the disk: it does
not still list what was just cleaned, and the totals do not keep counting it.

## What can be cleaned

DiskGOup will not stage anything a protection rule covers. There are two
tiers, and they behave differently — see
[Protection rules](/reference/protection/) for the full detail.

| Tier | What it refuses | Effect |
|---|---|---|
| **Protected** | System roots, system-marked entries, game data and saves | The whole subtree is off limits |
| **Critical** | The volume root, the users container, a home directory | The *container* is refused; what is inside it stays cleanable |

```
refused /Users/you: This folder is required by the system or your account and cannot be cleaned.
refused ~/Library/Caches/app: System folders cannot be cleaned.
```

A home directory is refused **as an item**, but `~/Library/Caches/app` inside
it is perfectly cleanable — that is the difference between the two tiers.

## Finding what is safe to remove

DiskGOup can work out the junk on its own. A folder named `cache`, `logs`,
`temp` or `tmp` — and everything below it — is what the operating system
regenerates.

```bash
diskgoup --json cleanup stage ~/Library/Caches/example
```

The desktop app's "Safe to clean" view lists exactly these folders: the
**top-most** cache folders of the scan, biggest first. A cache folder inside
another cache folder is part of its parent, so the space is counted once.

Downloads, documents and the trash are deliberately **not** included — they
are the user's own data, not something the system regenerates.

## In the desktop app

The Cleanup dialog walks the same flow, one step at a time: pick items, review
the list, validate, confirm. The index correction happens automatically.

## Safety rules in the codebase

DiskGOup deletes files, which makes some rules non-negotiable:

- Nothing is deleted without being staged, reviewed, validated and confirmed.
- The staged list is revalidated immediately before anything moves.
- Items go to the platform recycle bin, never to `unlink`.
- Protected paths can never be staged.
- There is no code path that deletes files outside the staged flow — not even
  "temporarily", not even for a cache.
