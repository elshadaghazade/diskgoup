---
title: Games
description: The Steam and Epic libraries, the size of every game and what it holds.
---

![The Games section](/app/17-games.png)

The Games section finds the local game libraries and measures them.

| Platform | Where it looks |
|---|---|
| **Steam** | `steamapps/libraryfolder.vdf` lists the library roots; each library holds `steamapps/common/<Game>` and the `appmanifest_<appid>.acf` files. |
| **Epic** | The Epic Games Launcher directory. |

The switcher above the header filters by platform. Every library is a panel
with its games, the size of each game and the categories it holds — game
files, saves, workshop mods.

:::caution
Measured game size is **not** reclaimable space. Saves and game files are
protected: they cannot be cleaned, and removing a game entry only changes the
inventory — it never touches the game.
:::

See [Games](/guide/games/) for the command-line equivalent.
