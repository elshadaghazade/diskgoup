// Checks that the packaged macOS app really carries a code signature.
//
// electron-builder 26 signs the bundle itself (the ad-hoc identity "-" in
// package.json) and verifies the result, so this script signs nothing — it
// only asserts that the signature is there, that it seals the bundle's
// resources, and that it belongs to DiskGOup and not to the stock Electron
// bundle we start from.
//
// It is wired into electron-builder as the `afterSign` hook, so a build that
// produced a broken seal fails right where it happens. It can also be run on
// its own, which is what the release workflow does:
//
//   node scripts/verify-signature.mjs [path/to/DiskGOup.app]
//
// Without an argument it looks for the packaged app under ./release.
//
// The hook fires on every platform, so everything here is a no-op off macOS.

import { spawnSync } from 'node:child_process'
import { existsSync, readdirSync } from 'node:fs'
import { join, resolve } from 'node:path'
import { pathToFileURL } from 'node:url'

const DEFAULT_IDENTIFIER = 'app.diskgoup.desktop'
const RELEASE_DIR = 'release'

function die(msg) {
  console.error(`\n✗ ${msg}\n`)
  process.exit(1)
}

function codesign(args) {
  const result = spawnSync('codesign', args, { encoding: 'utf8' })
  if (result.error) {
    die(`could not run codesign: ${result.error.message}`)
  }
  return {
    status: result.status,
    // codesign prints its findings on stderr, its errors on stdout.
    output: `${result.stdout ?? ''}\n${result.stderr ?? ''}`,
  }
}

// Every .app below `dir`, at most three levels deep.
function findApps(dir, depth = 0) {
  if (depth > 3 || !existsSync(dir)) return []
  const found = []
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    if (!entry.isDirectory()) continue
    const full = join(dir, entry.name)
    if (entry.name.endsWith('.app')) {
      found.push(full)
      continue
    }
    found.push(...findApps(full, depth + 1))
  }
  return found
}

function verifyApp(appPath, expectedIdentifier) {
  const check = codesign(['--verify', '--deep', '--strict', appPath])
  if (check.status !== 0) {
    die(
      `codesign --verify --deep --strict failed for ${appPath}\n${check.output.trim()}\n` +
        `The bundle is not signed properly — macOS will treat it as damaged.`
    )
  }

  const details = codesign(['-dv', '--verbose=2', appPath]).output
  const identifier = details.match(/^Identifier=(.*)$/m)?.[1]?.trim()
  const signature = details.match(/^Signature=(.*)$/m)?.[1]?.trim()
  // "Sealed Resources version=2 rules=13 files=14" — or "Sealed Resources=none".
  const sealed = details.match(/^Sealed Resources[=\s]+(.*)$/m)?.[1]?.trim()

  if (!identifier) {
    die(`${appPath} carries no signature at all — the bundle was never signed.`)
  }
  if (identifier !== expectedIdentifier) {
    die(
      `${appPath} is signed as "${identifier}" instead of "${expectedIdentifier}" — ` +
        `the bundle was never re-signed, it only carries Electron's own signature.`
    )
  }
  if (!sealed || sealed.startsWith('none')) {
    die(`${appPath} has no sealed resources — the signature covers no files.`)
  }

  console.log(`✓ ${appPath}`)
  console.log(`  identifier: ${identifier}`)
  console.log(`  signature:  ${signature ?? 'unknown'}`)
  console.log(`  sealed:     ${sealed}`)
}

// electron-builder calls this after it has signed the bundle.
export async function afterSign(context) {
  if (process.platform !== 'darwin') return

  const appOutDir = context?.appOutDir
  const expectedIdentifier = context?.packager?.appInfo?.id ?? DEFAULT_IDENTIFIER
  const apps = appOutDir ? findApps(appOutDir) : findApps(resolve(RELEASE_DIR))
  if (apps.length === 0) {
    die(`no packaged .app found in ${appOutDir ?? RELEASE_DIR}`)
  }
  for (const app of apps) {
    verifyApp(app, expectedIdentifier)
  }
}

const invokedDirectly =
  process.argv[1] != null && import.meta.url === pathToFileURL(process.argv[1]).href

if (invokedDirectly) {
  if (process.platform !== 'darwin') {
    console.log('✓ not macOS — nothing to verify')
  } else {
    const argument = process.argv[2]
    const apps = argument ? [resolve(argument)] : findApps(resolve(RELEASE_DIR))
    if (apps.length === 0) {
      die(`no packaged .app found${argument ? '' : ` in ${RELEASE_DIR}`}`)
    }
    for (const app of apps) {
      verifyApp(app, DEFAULT_IDENTIFIER)
    }
  }
}
