---
title: Snapshots
description: The size history of a drive, with the growth of every file type.
---

![The Snapshots section](/app/19-snapshots.png)

A snapshot records the size of every file kind of a scan. **Save snapshot**
takes one and keeps it in the index, with its label, its total and the moment
it was taken.

The growth of a drive needs **two** snapshots: a current one and one taken at
least seven days earlier. With only one snapshot the section says so — *"No
comparable history"* — and shows the current usage instead of a made-up
change.

With a comparable history the header shows the current total and the
seven-day change, green for a shrink and red for a growth. The table below
breaks that change down per file type: the current size, the growth and the
share of the usage.

:::tip
A snapshot is cheap — it is a set of numbers, not a copy of the files. Taking
one every week is what makes the growth column meaningful.
:::

See [Snapshots](/guide/snapshots/) for the command-line equivalent.
