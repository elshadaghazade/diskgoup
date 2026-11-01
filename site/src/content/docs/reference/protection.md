---
title: Protection rules
description: What DiskGOup refuses to clean, and why — system roots, attributes, game data and critical containers.
---

A **protected** entry can be scanned, measured and reported — it just can
never be staged for deletion. This page is the complete list of the rules.

## Two tiers

| Tier | What it covers | Can it be staged? |
|---|---|---|
| **Protected** | System folders, game data, items the OS marks read-only. | ❌ Never. |
| **Critical** | The volume root, the users container, a home directory. | ❌ The container. Its **contents** are fine. |

The distinction matters: your home directory is critical, but a cache folder
inside it is cleanable.

## The refusal messages

These are the exact sentences the tool prints:

| Message | Why |
|---|---|
| `Protected game or application data cannot be staged.` | Game files, DLC or saved games. |
| `System folders cannot be cleaned.` | A system root or a system directory name. |
| `The operating system marks this item as system or read-only.` | The OS attributes say hands off. |
| `This folder is required by the system or your account and cannot be cleaned.` | A critical container. |

## Rule 1 — system roots

Per-platform prefixes that always hold the OS and its core applications.

### macOS

```
/System          /Library            /Applications
/private/etc     /private/var/db     /private/var/log
/private/var/vm  /private/var/root   /cores
/dev             /Volumes/Preboot    /Volumes/Recovery
/Volumes/VM      /Volumes/Update
```

### Windows

```
C:\Windows                     C:\Program Files
C:\Program Files (x86)         C:\ProgramData
C:\System Volume Information   C:\Recovery
C:\$Recycle.Bin
```

### Linux

```
/bin      /sbin     /usr      /etc      /boot     /lib
/lib32    /lib64    /opt      /proc     /sys      /dev
/run      /snap     /var/lib  /var/cache
```

### The macOS data volume

On macOS the writable volume is mounted **inside** the sealed system volume,
at `/System/Volumes/Data`. Its contents mirror `/` — `/Users`,
`/Applications`, `/Library` and `/private` are firmlinks into it.

That means `/System/Volumes/Data/Users/me` and `/Users/me` are the same
place. Before any rule is applied, that prefix is **folded away**: the data
volume becomes the root it mirrors. Without this, the macOS rules would miss
half of the disk.

## Rule 2 — system directory names

Ten names are reserved, and they only count **at the top of a volume**:

```
windows   system volume information   $recycle.bin   system32
syswow64  winsxs   recovery   preboot   vm   update
```

Only the first path component is checked. `/vm` and `/update` are system
directories; a folder *you* named `vm` — `~/vm`, `~/REPOS/update` — is
ordinary content, and refusing those would refuse a large part of a normal
home directory.

## Rule 3 — platform attributes

| Platform | Attribute | Meaning |
|---|---|---|
| Windows | `FILE_ATTRIBUTE_SYSTEM` (`0x4`) | A system file. |
| Unix | `UF_IMMUTABLE`, `UF_APPEND` | A deliberate "hands off". |
| macOS | `UF_HIDDEN` | Only counts **inside a system root**. |

The macOS hidden flag is the interesting one. Every dotfile in a home
directory carries it, and refusing those would refuse exactly the files a
user expects to clean — so it only means something inside a protected system
root.

## Rule 4 — semantic role

The **`game`** kind is protected. A file inside a game folder is game data
too — the check looks at the parent's kind as well as the entry's own.

Game data is not reclaimable space: removing it frees bytes you cannot get
back, and a save is not yours to throw away.

## Rule 5 — critical containers

These may never be staged **as a whole**:

| Path | Why |
|---|---|
| The volume root (`/`, `C:`) | Removing it removes the volume. |
| Any other drive root (`D:`) | Same. |
| The users container (`/Users`, `C:\Users`, `/home`) | Removing it removes every account. |
| Any account's home directory | Removing it removes that account. |
| `/private` on macOS | The system-private data. |
| `~/Library` on macOS | Holds the user's application data. |
| `/root`, `~/.config`, `~/.local` on Linux | System and user configuration. |
| `%LOCALAPPDATA%` on Windows | The user's application data. |

This is an **exact-path** rule, not a subtree rule. The container is refused;
what is inside it is not. `~/Library/Caches` is cleanable, `~/Library` is
not.

## How the rules are decided

The scanner asks about **every** entry of a walk, so deciding protection per
entry by walking the rules again for each one would be wasteful. Instead:

- A `DirGuard` records what a directory has already established — whether it
  is protected, whether it is under a system root, and whether it sits at
  the top of a volume.
- A directory's children **inherit** that guard and only add their own name
  and flags. A system root, a system directory name or an attribute flag can
  only be introduced by an entry itself, never by one of its children.
- The hot path (`entry_is_protected`) reuses the guard and the `stat` result
  the caller already holds.

The decision itself lives in one place — `protection_reason()` — and the fast
path reaches the same verdict. The folder listing uses the same rule as the
cleanup gate, so a badge in the UI always tells the truth about what the
gate will do.

## What protection does *not* mean

Protected does not mean invisible, and it does not mean the file is
untouchable by you:

- Protected files are **still scanned** and **still reported**. The system
  volume shows up in the treemap like anything else.
- Protection only applies to DiskGOup's own cleanup. Your own file manager
  can do what it likes.
- Protection is decided **live**, not read from the index. A scan made
  before the rules changed would otherwise report every item as protected.

## See also

- [Cleaning up safely](/guide/cleanup/) — the staged-item workflow.
- [File kinds](/reference/file-kinds/) — how a folder gets the `game` kind.
