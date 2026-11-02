# DiskGOup documentation

The documentation site for [DiskGOup](https://github.com/elshadaghazade/diskgoup),
built with [Astro](https://astro.build/) and
[Starlight](https://starlight.astro.build/).

Live at **https://diskgoup.vercel.app**.

The site lives in the app repository, under `site/`. It is its own Astro
project with its own dependencies — the app's Python and Electron code is
untouched by it.

## Requirements

- **Node 24** (see `.nvmrc`) — Astro 7 needs a recent Node. If you use nvm, run
  `nvm use` in this folder before anything else.
- **Yarn** 1.x

## Commands

```bash
yarn install     # install dependencies
yarn dev         # dev server on http://localhost:4321
yarn build       # static build into dist/
yarn preview     # serve the built site
yarn astro       # astro CLI (add integrations, etc.)
```

## Deploying

The site deploys to Vercel; the folder is linked to the project
`elshadaghazades-projects/diskgoup`.

```bash
nvm use          # Node 24 — Astro 7 refuses anything below 22.23.4
vercel --prod    # production
vercel           # preview
```

The project's **Node.js Version must be 24.x** — the version in `.nvmrc`, and
the version Astro 7 needs. Vercel creates new projects with the newest Node
release, which is often one Astro does not support yet; if the build fails with
`Found invalid or discontinued Node.js Version`, fix it in the project's
settings.

`astro.config.mjs` reads `VERCEL_PROJECT_PRODUCTION_URL` / `VERCEL_URL` so the
canonical URLs and the sitemap point at whichever host the site is served
from. No domain is hard-coded, and there is no `base` path — the site is
served from the root.

Vercel detects the Astro framework preset on its own, so there is no
`vercel.json` to keep in sync. `.vercelignore` keeps the local `dist/` and
`.astro/` out of the upload — Vercel builds those itself.

Note that the Vercel CLI reads **`.vercelignore`, not `.gitignore`**, when it
collects the files to upload. The `dist/` and `.astro/` entries in
`.gitignore` do not keep them out of a deploy — only `.vercelignore` does.

## Layout

```
src/
├── assets/                # the app logo (SVG)
├── content.config.ts     # the docs content collection (Starlight schema)
└── content/docs/         # one .md / .mdx file per page
astro.config.mjs          # Starlight config: title, logo, sidebar, social links
public/                   # static assets (favicon, images)
scripts/make-logo.py      # draws the logo from the app icon's geometry
```

## The logo

The site shows the app's own icon — the donut chart on the dark squircle —
next to the title and in the browser tab.

`src/assets/logo.svg` and `public/favicon.svg` are the same artwork: the
vector version of the app icon. `scripts/make-logo.py` draws it from the same
geometry and palette as `electron/scripts/make-icon.py`, which draws the raster
app icon, so the two never drift apart:

```bash
python3 scripts/make-logo.py
```

Run it after the app icon changes, and commit the result.

Pages are plain Markdown with frontmatter:

```md
---
title: Page title
description: One-line summary, used for search and SEO.
---
```

## Adding a page

1. Write the page as a `.md` file under `src/content/docs/`. Use `.mdx` only
   when the page needs Starlight's JSX components (`<Card>`, `<CardGrid>`) —
   the homepage is the one `.mdx` page today.
2. Add it to the `sidebar` array in `astro.config.mjs`. The sidebar is
   explicit, so a page that is not listed there is still reachable by URL but
   will not appear in the navigation.
3. Run `yarn build` — Starlight fails the build if a sidebar entry points at a
   slug that does not exist.

A file named `index.md` inside a folder gets the **folder's** slug, not
`folder/index`, so `reference/index.md` would be `/reference/`. Name such
pages after what they are: `reference/scan-index.md`.

## The structure of the site

| Section | Pages |
|---|---|
| **Getting started** | Installation · Quick start · Where things are stored |
| **Guides** | Scanning · Explore views · Searching · Finding duplicates · Cleaning up safely · Archives · Applications · Games · Live monitor · Snapshots · Reports |
| **Desktop app** | The desktop app · Explore · Search · Archives · Duplicates · Applications · Games · Monitor · Snapshots · Reports |
| **Reference** | CLI reference · JSON-RPC protocol · File kinds · Protection rules · The scan index · Environment variables |
| **Development** | Architecture · The desktop app · Building and releasing · Contributing |

The pages under **Desktop app** describe the Electron app and carry
screenshots of it. The screenshots are taken from a sample disk — a synthetic
folder tree and a made-up inventory — so no real file of yours is in them.
The images live in `public/app/` and are referenced as `/app/<name>.png`.

## What the site documents

The **shipped** behaviour of the CLI. Where the app's own notes in
`../docs/ARCHITECTURE.md` mark a module as "(planned)" but the code implements
it, the site describes what the code actually does.

When a command's flags, a default or an output format changes, update the
matching page in the same change. The
[CLI reference](src/content/docs/reference/cli.md) and the
[JSON-RPC protocol](src/content/docs/reference/json-rpc.md) go stale the
fastest.
