---
title: Archives
description: Look inside ZIP archives without extracting anything.
---

![The Archives section](/app/13-archives.png)

The archive browser is **read-only**. Nothing is extracted, nothing is
executed, and no file is written anywhere.

The first panel lists the ZIP archives the scan found, with their size. Click
one to open it; the second panel lists what is inside, with the uncompressed
size, the compressed size and the compression ratio of every member. A member
with an encrypted name carries a badge.

Click a member to preview it. The preview reads at most 64 KiB of the file and
shows it as text; a binary member gets a short explanation instead of a wall
of bytes.

![A preview of one member](/app/14-archives-preview.png)

The archive browser is the same one the CLI offers — see
[Archives](/guide/archives/).
