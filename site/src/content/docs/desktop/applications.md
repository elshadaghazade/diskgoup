---
title: Applications
description: The installed applications, the space they take and how to remove one.
---

![The Applications section](/app/16-applications.png)

The Applications section is an inventory of what is installed on the machine,
with the space each program occupies.

| Platform | Where it looks |
|---|---|
| **macOS** | `.app` bundles in `/Applications` and `~/Applications` |
| **Linux** | `.desktop` entries and the packages of the common prefixes |
| **Windows** | The entries of the uninstall registry |

The header counts the applications and adds up their size. Every row shows the
name, the version, the size and where the program lives.

## Removing one

**Remove** opens a dialog with the path and the size of the application and
offers the two ways out:

- **Move to Trash** — recoverable. The space comes back when the Trash is
  emptied.
- **Delete permanently** — a second confirmation, because it cannot be undone.

An application that belongs to the operating system carries a **system** badge
and its button is disabled — the reason is in the tooltip.

:::caution
Removing an application takes away the **program**. Its own data — settings,
documents, saved games — is left where it is. Uninstalling an application is
not a way to free space: the space it occupies comes back with the program
gone, but the data it wrote stays.
:::

See [Applications](/guide/applications/) for the command-line equivalent.
