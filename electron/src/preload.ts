// Preload script — runs in an isolated context and exposes a small, typed
// bridge to the renderer. The renderer never touches Node or Electron
// directly; everything goes through `window.diskgoup`.

import { contextBridge, ipcRenderer } from 'electron'

export type BackendStatus = {
  running: boolean
  pid?: number
  binaryPath?: string
  lastError?: string
  missing?: boolean
}

export type RpcNotification = { method: string; params: unknown }

const api = {
  /** The host platform — macOS draws its window controls over the topbar. */
  platform: process.platform,

  /** Call a method on the DiskGOup CLI. */
  call: <T = unknown>(method: string, params?: Record<string, unknown>): Promise<T> =>
    ipcRenderer.invoke('cli:call', method, params ?? {}),

  /** Current CLI status — used for the connection indicator. */
  getStatus: (): Promise<BackendStatus> => ipcRenderer.invoke('cli:status'),

  /** Subscribe to CLI status changes. Returns an unsubscribe function. */
  onStatus: (cb: (s: BackendStatus) => void): (() => void) => {
    const fn = (_e: unknown, s: BackendStatus): void => cb(s)
    ipcRenderer.on('cli:status', fn)
    return () => ipcRenderer.off('cli:status', fn)
  },

  /** Subscribe to CLI notifications (scan progress, duplicate stages). */
  onNotification: (cb: (n: RpcNotification) => void): (() => void) => {
    const fn = (_e: unknown, n: RpcNotification): void => cb(n)
    ipcRenderer.on('cli:notification', fn)
    return () => ipcRenderer.off('cli:notification', fn)
  },

  /** One-shot info about the app itself. */
  info: (): Promise<{
    version: string
    platform: NodeJS.Platform
    packaged: boolean
    cliPath: string
  }> => ipcRenderer.invoke('app:info'),

  /** Reveal a path in the OS file manager. */
  openPath: (path: string): Promise<string> => ipcRenderer.invoke('shell:open', path),
}

contextBridge.exposeInMainWorld('diskgoup', api)

export type DiskgoupBridge = typeof api
