/** Types mirroring the DiskGOup CLI's JSON payloads. */

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

/**
 * A pointer to the scan a view should read.
 *
 * `scanId` names one scan in the CLI's index. Sending it means the CLI reads
 * that exact scan instead of looking for one by path — so opening a scan from
 * the scan list never re-walks the disk.
 */
export type ScanRef = {
  path: string
  scanId?: number
}

export type Entry = {
  path: string
  name: string
  is_dir: boolean
  size: number
  on_disk: number
  mtime: number
  kind: string
  protected: boolean
  depth: number
  children?: Entry[]
}

export type KindTotal = {
  kind: string
  size: number
  files: number
  share: number
}

/**
 * One entry inside a folder of a scan.
 *
 * `files` and `folders` count what is inside a directory: the files of its
 * whole subtree and its immediate subfolders.
 */
export type BrowserEntry = {
  name: string
  path: string
  is_dir: boolean
  size: number
  on_disk: number
  kind: string
  protected: boolean
  mtime: number
  files: number
  folders: number
}

/** One step of the path breadcrumb. */
export type Crumb = {
  name: string
  path: string
}

/** The contents of one folder of a scan. */
export type BrowserFolder = {
  scan: ScanMeta
  path: string
  parent: string | null
  crumbs: Crumb[]
  /**
   * The folder changed on disk and is too big to be refreshed on its own.
   * The user can refresh it by hand.
   */
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

export type AgeBucket = {
  label: string
  size: number
  files: number
  max_days: number | null
  share: number
}

export type Rect = { x: number; y: number; width: number; height: number }

export type LayoutItem = {
  path: string
  name: string
  size: number
  kind: string
  depth: number
  color: string
  parent_path: string | null
  rect?: Rect
  start_angle?: number
  end_angle?: number
  radius?: number
  x?: number
  y?: number
}

export type LayoutResponse = {
  scan: ScanMeta
  view: string
  items: LayoutItem[]
}

export type SearchMatch = {
  path: string
  name: string
  is_dir: boolean
  size: number
  on_disk: number
  mtime: number
  kind: string
  protected: boolean
}

export type SearchResponse = {
  scan: ScanMeta
  query: Record<string, unknown>
  total: number
  page: number
  per_page: number
  pages: number
  matches: SearchMatch[]
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
  scan: ScanMeta
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

export type GameEntry = {
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
  categories: GameEntry[]
}

export type GameLibrary = {
  platform: string
  root: string
  size: number
  games: Game[]
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
}

export type MonitorSample = {
  timestamp: number
  network: { down: number; up: number }
  disk: {
    read: number
    write: number
    usage: number
    total: number
    used_percent: number
  }
  processes: { pid: number; name: string; cpu: number; memory: number }[]
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

export type StagedItem = {
  path: string
  size: number
  kind: string
  added_at: number
}

export type BackendStatus = {
  running: boolean
  pid?: number
  binaryPath?: string
  lastError?: string
  missing?: boolean
}

export type RpcNotification = { method: string; params: unknown }
