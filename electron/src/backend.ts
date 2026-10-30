// The bridge to the DiskGOup CLI.
//
// The CLI is the product: the Electron app owns no disk logic. It spawns the
// compiled binary as a child process and talks to it over a newline-delimited
// JSON-RPC channel on stdin/stdout (`diskgoup serve --quiet`).
//
// The binary is located in three places, in order:
//   1. packaged  → <app>/Contents/Resources/diskgoup   (electron-builder copies
//                  resources/diskgoup into the bundle via `extraResources`)
//   2. dev       → electron/resources/diskgoup         (built by scripts/build-cli.mjs)
//   3. fallback  → <repo>/dist/diskgoup                (the raw PyInstaller output)
//
// If none of them exists the app refuses to pretend it works: it reports the
// missing binary so the UI can tell the user exactly what to run.

import { spawn, type ChildProcess } from 'node:child_process'
import { existsSync } from 'node:fs'
import { join } from 'node:path'
import { app } from 'electron'

export type RpcNotification = { method: string; params: unknown }

export type BackendStatus = {
  running: boolean
  pid?: number
  binaryPath?: string
  lastError?: string
  /** Set when the binary could not be found at all. */
  missing?: boolean
}

type Pending = {
  resolve: (value: unknown) => void
  reject: (reason: Error) => void
}

let proc: ChildProcess | null = null
let lastError: string | undefined
let buffer = ''
let nextId = 1
const pending = new Map<number, Pending>()
const notificationListeners = new Set<(n: RpcNotification) => void>()
const statusListeners = new Set<(s: BackendStatus) => void>()

/** The binary's file name for the current platform. */
function binaryName(): string {
  return process.platform === 'win32' ? 'diskgoup.exe' : 'diskgoup'
}

/**
 * Resolve the CLI binary. Returns the path even when it does not exist, so
 * the caller can produce a precise error message.
 */
export function resolveBinary(): string {
  const name = binaryName()
  if (app.isPackaged) return join(process.resourcesPath, name)
  const dev = join(app.getAppPath(), 'resources', name)
  if (existsSync(dev)) return dev
  return join(app.getAppPath(), '..', 'dist', name)
}

/** True when the CLI binary is present and ready to run. */
export function binaryExists(): boolean {
  return existsSync(resolveBinary())
}

/** A human-readable explanation of how to produce the missing binary. */
export function missingBinaryMessage(): string {
  return [
    'The DiskGOup CLI binary was not found.',
    '',
    `Expected: ${resolveBinary()}`,
    '',
    'Build it with:',
    '  uv run pyinstaller diskgoup.spec',
    '  npm run build:cli          (in electron/)',
  ].join('\n')
}

export function getStatus(): BackendStatus {
  return {
    running: !!proc && proc.exitCode === null,
    pid: proc?.pid,
    binaryPath: resolveBinary(),
    lastError,
    missing: !binaryExists(),
  }
}

export function onStatus(fn: (s: BackendStatus) => void): () => void {
  statusListeners.add(fn)
  return () => statusListeners.delete(fn)
}

export function onNotification(fn: (n: RpcNotification) => void): () => void {
  notificationListeners.add(fn)
  return () => notificationListeners.delete(fn)
}

function emitStatus(): void {
  const status = getStatus()
  for (const fn of statusListeners) fn(status)
}

function handleLine(line: string): void {
  let message: Record<string, unknown>
  try {
    message = JSON.parse(line)
  } catch {
    // Not protocol traffic — the CLI may print a warning. Ignore it.
    return
  }

  const id = message.id
  if (typeof id === 'number' && pending.has(id)) {
    const entry = pending.get(id)!
    pending.delete(id)
    if (message.error) {
      const error = message.error as { message?: string }
      entry.reject(new Error(error.message ?? 'unknown error'))
    } else {
      entry.resolve(message.result)
    }
    return
  }

  // A notification has a method but no id.
  if (typeof message.method === 'string') {
    const notification: RpcNotification = {
      method: message.method,
      params: message.params,
    }
    for (const fn of notificationListeners) fn(notification)
  }
}

/** Start the CLI child process. Idempotent. */
export function start(): BackendStatus {
  if (proc && proc.exitCode === null) return getStatus()

  const binary = resolveBinary()
  if (!existsSync(binary)) {
    lastError = missingBinaryMessage()
    emitStatus()
    return getStatus()
  }

  lastError = undefined
  buffer = ''

  const child = spawn(binary, ['serve', '--quiet'], {
    stdio: ['pipe', 'pipe', 'pipe'],
    windowsHide: true,
    env: { ...process.env },
  })
  proc = child

  child.stdout?.on('data', (chunk: Buffer) => {
    buffer += chunk.toString()
    let index = buffer.indexOf('\n')
    while (index !== -1) {
      const line = buffer.slice(0, index).trim()
      buffer = buffer.slice(index + 1)
      if (line) handleLine(line)
      index = buffer.indexOf('\n')
    }
  })

  child.stderr?.on('data', (chunk: Buffer) => {
    const text = chunk.toString().trim()
    if (text) console.log(`[cli] ${text}`)
  })

  child.on('error', (err) => {
    lastError = err.message
    emitStatus()
  })

  child.on('exit', (code, signal) => {
    console.log(`[cli] exited code=${code} signal=${signal}`)
    if (code !== 0 && code !== null) lastError = `CLI exited with code ${code}.`
    // Reject everything still in flight so the renderer is not left hanging.
    for (const [, entry] of pending) entry.reject(new Error('the CLI exited'))
    pending.clear()
    if (proc === child) proc = null
    emitStatus()
  })

  emitStatus()
  return getStatus()
}

/** Stop the CLI child process. */
export function stop(): void {
  if (!proc) return
  const child = proc
  try {
    child.kill('SIGTERM')
  } catch {
    /* ignore */
  }
  setTimeout(() => {
    if (child.exitCode === null) {
      try {
        child.kill('SIGKILL')
      } catch {
        /* ignore */
      }
    }
  }, 2000)
  proc = null
  emitStatus()
}

/**
 * Call a method on the CLI and wait for its response.
 */
export function call<T = unknown>(method: string, params: Record<string, unknown> = {}): Promise<T> {
  if (!proc || proc.exitCode !== null) {
    return Promise.reject(new Error('the DiskGOup CLI is not running'))
  }
  const id = nextId++
  const payload = JSON.stringify({ id, method, params }) + '\n'
  return new Promise<T>((resolve, reject) => {
    pending.set(id, { resolve: resolve as (v: unknown) => void, reject })
    proc!.stdin?.write(payload)
  })
}
