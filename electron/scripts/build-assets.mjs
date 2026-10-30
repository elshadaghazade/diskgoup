// Copies the built Vite UI into the Electron app's dist/renderer/.
//
// The CLI binary is copied by build-cli.mjs; this script is strictly
// UI-copying, kept as a separate step so the pipeline stays linear
// (tsc → pyinstaller → assets → electron-builder).

import { existsSync, mkdirSync, cpSync } from 'node:fs'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = dirname(fileURLToPath(import.meta.url))
const root = resolve(__dirname, '..') // electron/
const repo = resolve(root, '..') // diskgoup-alternative/
const uiDist = join(repo, 'ui', 'dist')
const rendererOut = join(root, 'dist', 'renderer')

function die(msg) {
  console.error(`\n✗ ${msg}\n`)
  process.exit(1)
}

if (!existsSync(join(uiDist, 'index.html'))) {
  die(`Missing ${uiDist}/index.html — run "npm run build" in ui/ first.`)
}

mkdirSync(dirname(rendererOut), { recursive: true })
cpSync(uiDist, rendererOut, { recursive: true })
console.log(`✓ renderer: ${uiDist} → ${rendererOut}`)
