/**
 * The typed client for the DiskGOup CLI.
 *
 * Every call goes through the Electron preload bridge to the CLI child
 * process. The renderer never touches the filesystem itself.
 */

import type {
  AgeBucket,
  Application,
  ArchiveListing,
  Comparison,
  DuplicateResponse,
  GameLibrary,
  KindTotal,
  LayoutResponse,
  MonitorSample,
  ScanMeta,
  ScanRef,
  SearchResponse,
  SizeEntry,
  Snapshot,
  StagedItem,
  Volume,
} from './types'

export type RpcResult<T> = { ok: true; result: T } | { ok: false; error: string }

type Bridge = {
  platform: string
  call: <T = unknown>(
    method: string,
    params?: Record<string, unknown>,
  ) => Promise<RpcResult<T>>
  getStatus: () => Promise<import('./types').BackendStatus>
  onStatus: (cb: (s: import('./types').BackendStatus) => void) => () => void
  onNotification: (cb: (n: import('./types').RpcNotification) => void) => () => void
  info: () => Promise<{
    version: string
    platform: string
    packaged: boolean
    cliPath: string
  }>
  openPath: (path: string) => Promise<string>
}

declare global {
  interface Window {
    diskgoup: Bridge
  }
}

export function bridge(): Bridge {
  const value = window.diskgoup
  if (!value) {
    throw new Error('The DiskGOup bridge is unavailable — the preload script did not run.')
  }
  return value
}

/** Call a CLI method and unwrap the result, throwing on error. */
export async function call<T>(
  method: string,
  params: Record<string, unknown> = {},
): Promise<T> {
  const response = await bridge().call<T>(method, params)
  if (!response.ok) throw new Error(response.error)
  return response.result
}

/**
 * Turn a scan reference into CLI parameters.
 *
 * `scan_id` pins the read to one scan in the index. Without it the CLI looks
 * for a scan of that path — and scans the disk when it finds none.
 */
function refParams(ref: ScanRef): { path: string; scan_id?: number } {
  return ref.scanId === undefined
    ? { path: ref.path }
    : { path: ref.path, scan_id: ref.scanId }
}

export const api = {
  info: () => bridge().info(),
  status: () => bridge().getStatus(),
  onStatus: (cb: Parameters<Bridge['onStatus']>[0]) => bridge().onStatus(cb),
  onNotification: (cb: Parameters<Bridge['onNotification']>[0]) =>
    bridge().onNotification(cb),
  openPath: (path: string) => bridge().openPath(path),

  volumes: () => call<{ volumes: Volume[] }>('drives.list'),
  scans: () => call<{ scans: ScanMeta[] }>('scans.list'),

  /** Remove a scan and everything recorded for it from the index. */
  removeScan: (scanId: number) =>
    call<{ removed: ScanMeta }>('scans.remove', { scan_id: scanId }),

  scan: (path: string) =>
    call<ScanMeta & { canceled: boolean }>('scan.run', { path }),

  /** Hold a running scan at its next checkpoint. */
  pauseScan: () => call<{ paused: boolean }>('scan.pause'),

  /** Let a paused scan continue. */
  resumeScan: () => call<{ paused: boolean }>('scan.resume'),

  /** Stop a running scan. It stays in the index, marked incomplete. */
  cancelScan: () => call<{ canceled: boolean }>('scan.cancel'),

  tree: (ref: ScanRef) =>
    call<{ scan: ScanMeta; tree: import('./types').Entry | null }>('explore.tree', {
      ...refParams(ref),
    }),

  /**
   * The contents of one folder of the scan.
   *
   * Read from the index — opening a folder never re-walks the disk, unless
   * the folder changed and is small enough to be refreshed on the spot.
   */
  browse: (ref: ScanRef, path: string) =>
    call<import('./types').BrowserFolder>('explore.children', {
      ...refParams(ref),
      path,
    }),

  /**
   * The space that can be reclaimed safely.
   *
   * The cache folders of the scan — the ones the operating system
   * regenerates. The answer has the shape of a folder listing, so the
   * browser draws it with the same cards.
   */
  reclaimable: (ref: ScanRef) =>
    call<import('./types').BrowserFolder>('explore.reclaimable', refParams(ref)),

  /**
   * Walk one folder of the scan again and correct the index.
   *
   * Only the folder is walked — the rest of the scan keeps what it holds.
   */
  refresh: (ref: ScanRef, path: string) =>
    call<{
      scan: ScanMeta
      path: string
      files: number
      folders: number
      bytes: number
      changed: boolean
    }>('scan.refresh', { ...refParams(ref), path }),
  sizes: (ref: ScanRef, limit = 50) =>
    call<{ scan: ScanMeta; entries: SizeEntry[] }>('explore.sizes', {
      ...refParams(ref),
      limit,
    }),
  types: (ref: ScanRef) =>
    call<{ scan: ScanMeta; types: KindTotal[] }>('explore.types', refParams(ref)),
  age: (ref: ScanRef) =>
    call<{ scan: ScanMeta; buckets: AgeBucket[] }>('explore.age', refParams(ref)),

  layout: (ref: ScanRef, view: string, depth = 3) =>
    call<LayoutResponse>('view.layout', { ...refParams(ref), view, depth }),

  search: (ref: ScanRef, params: Record<string, unknown>) =>
    call<SearchResponse>('search.query', { ...refParams(ref), ...params }),

  duplicates: (ref: ScanRef) => call<DuplicateResponse>('duplicates.find', refParams(ref)),

  archives: (archive: string, prefix = '') =>
    call<ArchiveListing>('archives.list', { archive, prefix }),
  archivePreview: (archive: string, member: string) =>
    call<{
      text: string | null
      truncated: boolean
      binary: boolean
      encrypted: boolean
      empty: boolean
      reason: string | null
    }>('archives.preview', { archive, member }),

  games: () => call<{ libraries: GameLibrary[]; total_size: number }>('games.list'),

  apps: () => call<{ applications: Application[]; total_size: number }>('apps.list'),

  monitor: () => call<MonitorSample>('monitor.sample', { processes: 10 }),

  snapshots: (ref: ScanRef) =>
    call<{ scan: ScanMeta; snapshots: Snapshot[] }>('snapshots.list', refParams(ref)),
  saveSnapshot: (ref: ScanRef, label?: string) =>
    call<Snapshot>('snapshots.save', { ...refParams(ref), label }),
  compareSnapshots: (ref: ScanRef) =>
    call<Comparison>('snapshots.compare', refParams(ref)),

  weeklyReport: (ref: ScanRef) =>
    call<{ scan: ScanMeta; html: string }>('reports.weekly', refParams(ref)),
  typesReport: (ref: ScanRef) =>
    call<{ scan: ScanMeta; csv: string }>('reports.types', refParams(ref)),

  stageCleanup: (ref: ScanRef, paths: string[]) =>
    call<{ staged: StagedItem[]; refused: { path: string; reason: string }[] }>(
      'cleanup.stage',
      { ...refParams(ref), paths },
    ),
  /** Take items back off the review list. */
  unstage: (ref: ScanRef, paths: string[]) =>
    call<{ removed: number }>('cleanup.unstage', { ...refParams(ref), paths }),
  cleanupList: (ref: ScanRef) =>
    call<{ items: StagedItem[]; total: number }>('cleanup.list', refParams(ref)),
  cleanupValidate: (ref: ScanRef) =>
    call<{ valid: StagedItem[]; issues: { path: string; reason: string }[] }>(
      'cleanup.validate',
      refParams(ref),
    ),
  cleanupCommit: (ref: ScanRef, permanent = false) =>
    call<{
      moved: string[]
      failed: { path: string; reason: string }[]
      issues: { path: string; reason: string }[]
    }>('cleanup.commit', { ...refParams(ref), permanent }),
}
