// Checks that the packaged macOS app really carries a code signature.
//
// electron-builder 26 signs the bundle itself (the ad-hoc identity "-" in
// package.json) and verifies the result, so this script signs nothing — it
// only asserts that the signature is there, that it seals the bundle's
// resources, and that it belongs to DiskGOup and not to the stock Electron
// bundle we start from.
//
// When the build was given a certificate (CSC_LINK is set), the signature
// has to be a Developer ID one. An ad-hoc signature seals the bundle just
// as well, so without this check a build that silently failed to find the
// certificate would look exactly like a good one — and macOS would refuse
// to open the app.
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

// The release build sets CSC_LINK when a Developer ID certificate is
// configured — that is the signal that the app has to carry that
// signature, and not the ad-hoc one that only seals the bundle.
const requiresDeveloperId = Boolean(process.env.CSC_LINK)

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

  const details = codesign(['-dv', '--verbose=4', appPath]).output
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

  // When a certificate is configured, the signature has to be that one.
  //
  // An ad-hoc signature passes every check above — it seals the bundle and
  // carries the right identifier — but it proves nothing about who built
  // the app, and macOS refuses to open it. So the build says out loud that
  // it expects a Developer ID, and the signature has to be one.
  //
  // The Authority line is what says it: it names the certificate that
  // signed the bundle. An ad-hoc signature has no chain at all, and the
  // other Apple certificates name themselves differently.
  const team = details.match(/^TeamIdentifier=(.*)$/m)?.[1]?.trim()
  const authority = details.match(/^Authority=Developer ID Application:.*$/m)?.[0]

  if (requiresDeveloperId && !authority) {
    die(
      `${appPath} is not signed with a Developer ID certificate` +
        `${signature ? ` — it is signed "${signature}"` : ''}.` +
        `\nA Developer ID signature is what makes macOS open the app.`
    )
  }

  console.log(`✓ ${appPath}`)
  console.log(`  identifier: ${identifier}`)
  console.log(`  signature:  ${signature ?? 'unknown'}`)
  console.log(`  team:       ${team && team !== 'not set' ? team : 'none'}`)
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
