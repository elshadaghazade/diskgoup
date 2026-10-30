// Builds the DiskGOup CLI binary and copies it into electron/resources/.
//
// The Electron app spawns this binary as a child process, so it must exist
// both in development (resources/diskgoup) and inside the packaged app
// (electron-builder copies it to Contents/Resources via `extraResources`).
//
// Run automatically by `npm run dev` and `npm run build`.

import { spawnSync } from 'node:child_process'
import { existsSync, mkdirSync, cpSync, chmodSync, statSync } from 'node:fs'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = dirname(fileURLToPath(import.meta.url))
const root = resolve(__dirname, '..') // electron/
const repo = resolve(root, '..') // diskgoup-alternative/

const isWindows = process.platform === 'win32'
const binaryName = isWindows ? 'diskgoup.exe' : 'diskgoup'

function die(msg) {
  console.error(`\n✗ ${msg}\n`)
  process.exit(1)
}

// Resolve how to invoke PyInstaller:
//   1. .venv/bin/pyinstaller          — the conventional dev-dependency path
//   2. `uv run --with pyinstaller`    — ephemeral install, so a fresh checkout
//                                       works without a separate pip install
const venvPyinstaller = join(repo, '.venv', 'bin', 'pyinstaller')
const venvPyinstallerWin = join(repo, '.venv', 'Scripts', 'pyinstaller.exe')
let pyinstallerCmd
let pyinstallerArgs

if (existsSync(venvPyinstaller)) {
  pyinstallerCmd = venvPyinstaller
  pyinstallerArgs = ['diskgoup.spec']
} else if (existsSync(venvPyinstallerWin)) {
  pyinstallerCmd = venvPyinstallerWin
  pyinstallerArgs = ['diskgoup.spec']
} else {
  pyinstallerCmd = 'uv'
  pyinstallerArgs = ['run', '--with', 'pyinstaller', '--', 'pyinstaller', 'diskgoup.spec']
}

console.log(`▶ ${pyinstallerCmd} ${pyinstallerArgs.join(' ')} (cwd=${repo})`)
const result = spawnSync(pyinstallerCmd, pyinstallerArgs, {
  cwd: repo,
  stdio: 'inherit',
  shell: isWindows,
})
if (result.status !== 0) {
  die(`pyinstaller exited with status ${result.status}`)
}

const src = join(repo, 'dist', binaryName)
const dst = join(root, 'resources', binaryName)

if (!existsSync(src)) {
  die(`expected ${src} after pyinstaller, but it is missing`)
}

mkdirSync(dirname(dst), { recursive: true })
// Overwrite the previous copy so a stale binary is never shipped.
cpSync(src, dst)
if (!isWindows) {
  chmodSync(dst, 0o755)
}
if (!(statSync(dst).mode & 0o111) && !isWindows) {
  die(`${dst} is not executable after the copy`)
}

console.log(`✓ CLI: ${src} → ${dst}`)
