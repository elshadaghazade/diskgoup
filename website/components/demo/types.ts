/**
 * The types the demo exchanges with the sample data.
 *
 * They mirror the CLI's JSON payloads — the same shapes the desktop app
 * receives over JSON-RPC — so the components below are the real ones with
 * a different data source.
 */

export type Volume = {
  device: string
  mountpoint: string
  label: string
  fstype: string
  total: number
  used: number
  free: number
  used_percent: number
  removable: boolean
}

export type ScanMeta = {
  scan_id: number
  root: string
  started_at: number
  finished_at: number
  duration: number
  total_size: number
  total_on_disk: number
  files: number
  folders: number
  skipped: number
  complete: boolean
}

export type BrowserEntry = {
  name: string
  path: string
  is_dir: boolean
  size: number
  on_disk: number
  kind: string
  protected: boolean
  critical: boolean
  mtime: number
  files: number
  folders: number
  reason?: string | null
}

export type Crumb = {
  name: string
  path: string
}

export type BrowserFolder = {
  path: string
  parent: string | null
  crumbs: Crumb[]
  stale: boolean
  entries: BrowserEntry[]
}

export type SizeEntry = {
  name: string
  path: string
  is_dir: boolean
  size: number
  size_human: string
  on_disk: number
  kind: string
  protected: boolean
  share: number
}

export type KindTotal = {
  kind: string
  size: number
  files: number
  share: number
}

export type AgeBucket = {
  label: string
  size: number
  files: number
  max_days: number | null
  share: number
}

export type LayoutItem = {
  path: string
  name: string
  size: number
  kind: string
  depth: number
  color: string
  parent_path: string | null
  rect?: { x: number; y: number; width: number; height: number }
  start_angle?: number
  end_angle?: number
  radius?: number
  x?: number
  y?: number
}

export type DuplicateGroup = {
  sha256: string
  size: number
  copies: number
  reclaimable: number
  keep: string | null
  paths: string[]
}

export type DuplicateResponse = {
  groups: DuplicateGroup[]
  group_count: number
  total_reclaimable: number
  candidates: number
  skipped: { path: string; reason: string }[]
}

export type ArchiveEntry = {
  name: string
  is_dir: boolean
  size: number
  compressed: number
  ratio: number
  encrypted: boolean
}

export type ArchiveListing = {
  path: string
  items: number
  uncompressed: number
  compressed: number
  partial: boolean
  error: string | null
  entries: ArchiveEntry[]
}

export type ArchivePreview = {
  text: string | null
  truncated: boolean
  binary: boolean
  encrypted: boolean
  empty: boolean
  reason: string | null
}

/** One archive of the sample disk, with its listing and its previews. */
export type DemoArchive = {
  path: string
  size: number
  listing: ArchiveListing
  previews: Record<string, ArchivePreview>
}

export type Application = {
  id: string
  name: string
  path: string | null
  size: number
  version: string | null
  publisher: string | null
  uninstall_command: string | null
  source: string
  protected: boolean
  reason: string | null
}

export type GameCategory = {
  category: string
  size: number
  files: number
  protected: boolean
}

export type Game = {
  name: string
  platform: string
  path: string
  size: number
  files: number
  app_id: string | null
  protected: boolean
  categories: GameCategory[]
}

export type GameLibrary = {
  platform: string
  root: string
  size: number
  games: Game[]
}

export type MonitorProcess = {
  pid: number
  name: string
  cpu: number
  memory: number
}

export type MonitorSample = {
  timestamp: number
  network: { down: number; up: number }
  disk: { read: number; write: number; usage: number; total: number; used_percent: number }
  processes: MonitorProcess[]
}

export type Snapshot = {
  id: number
  scan_id: number
  label: string
  created_at: number
  total_size: number
  total_on_disk: number
  kinds: Record<string, number>
}

export type KindChange = {
  kind: string
  current: number
  baseline: number | null
  growth: number
  growth_percent: number
  share: number
}

export type Comparison = {
  has_history: boolean
  baseline: Snapshot | null
  total_current: number
  total_baseline: number | null
  total_growth: number
  changes: KindChange[]
}
