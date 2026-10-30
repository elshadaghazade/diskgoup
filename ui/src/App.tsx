import { useCallback, useEffect, useMemo, useState } from 'react'
import { api } from './lib/api'
import { bytes, count, duration, shortenPath, tailPath } from './lib/format'
import type { BackendStatus, ScanMeta, ScanRef, Volume } from './lib/types'
import Sidebar from './components/Sidebar'
import ConfirmDialog from './components/ConfirmDialog'
import Inspector from './components/Inspector'
import ExploreTab from './components/ExploreTab'
import SearchTab from './components/SearchTab'
import ArchivesTab from './components/ArchivesTab'
import DuplicatesTab from './components/DuplicatesTab'
import ApplicationsTab from './components/ApplicationsTab'
import GamesTab from './components/GamesTab'
import MonitorTab from './components/MonitorTab'
import SnapshotsTab from './components/SnapshotsTab'
import ReportsTab from './components/ReportsTab'

export type TabId =
  | 'explore'
  | 'search'
  | 'archives'
  | 'duplicates'
  | 'applications'
  | 'games'
  | 'monitor'
  | 'snapshots'
  | 'reports'

const TABS: { id: TabId; label: string }[] = [
  { id: 'explore', label: 'Explore' },
  { id: 'search', label: 'Search' },
  { id: 'archives', label: 'Archives' },
  { id: 'duplicates', label: 'Duplicates' },
  { id: 'applications', label: 'Applications' },
  { id: 'games', label: 'Games' },
  { id: 'monitor', label: 'Monitor' },
  { id: 'snapshots', label: 'Snapshots' },
  { id: 'reports', label: 'Reports' },
]

export type ScanProgress = {
  files: number
  folders: number
  bytes: number
  current: string | null
  elapsed: number
}

// macOS draws its window controls over the topbar, so the brand needs room
// for them.
const IS_MAC = window.diskgoup?.platform === 'darwin'

/** Arrows pointing outward — the side panels hide, the workspace widens. */
function ExpandIcon() {
  return (
    <svg width="15" height="15" viewBox="0 0 14 14" aria-hidden="true">
      <path
        d="M4.5 2 1.5 5l3 3M9.5 2l3 3-3 3"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.4"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  )
}

/** Arrows pointing inward — the side panels come back. */
function CollapseIcon() {
  return (
    <svg width="15" height="15" viewBox="0 0 14 14" aria-hidden="true">
      <path
        d="M1.5 2l3 3-3 3M12.5 2l-3 3 3 3"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.4"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  )
}

export default function App() {
  const [tab, setTab] = useState<TabId>('explore')
  const [volumes, setVolumes] = useState<Volume[]>([])
  const [scans, setScans] = useState<ScanMeta[]>([])
  const [scan, setScan] = useState<ScanMeta | null>(null)
  const [progress, setProgress] = useState<ScanProgress | null>(null)
  const [scanRoot, setScanRoot] = useState('')
  const [paused, setPaused] = useState(false)
  const [status, setStatus] = useState<BackendStatus | null>(null)
  const [filter, setFilter] = useState('')
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [pendingRemoval, setPendingRemoval] = useState<ScanMeta | null>(null)
  const [focus, setFocus] = useState(false)

  // Every view reads the scan this points at. The scan id pins the read to
  // one entry in the CLI's index, so opening a stored scan never re-walks
  // the disk.
  const scanRef = useMemo<ScanRef | null>(
    () => (scan ? { path: scan.root, scanId: scan.scan_id } : null),
    [scan],
  )

  useEffect(() => {
    api
      .volumes()
      .then((result) => setVolumes(result.volumes))
      .catch((err: Error) => setError(err.message))
  }, [])

  // The CLI is started before this window opens, so its "connected" status
  // event has already been sent. Read the current status once, then listen.
  useEffect(() => {
    api
      .status()
      .then(setStatus)
      .catch(() => undefined)
  }, [])

  // Open the newest stored scan so the app starts with data on screen
  // instead of an empty workspace.
  useEffect(() => {
    api
      .scans()
      .then((result) => {
        setScans(result.scans)
        const newest = result.scans.find((item) => item.complete) ?? result.scans[0]
        if (newest) setScan(newest)
      })
      .catch((err: Error) => setError(err.message))
  }, [])

  useEffect(() => api.onStatus(setStatus), [])

  useEffect(
    () =>
      api.onNotification((notification) => {
        if (notification.method === 'scan.progress') {
          setProgress(notification.params as ScanProgress)
        } else if (notification.method === 'scan.state') {
          const state = (notification.params as { state?: string }).state
          if (state === 'paused') setPaused(true)
          if (state === 'running') setPaused(false)
        }
      }),
    [],
  )

  // Escape leaves focus mode and brings the side panels back.
  useEffect(() => {
    if (!focus) return
    const onKey = (event: KeyboardEvent) => {
      // The confirm dialog owns Escape while it is open.
      if (event.key === 'Escape' && !pendingRemoval) setFocus(false)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [focus, pendingRemoval])

  const runScan = useCallback(async (target: string) => {
    setBusy(true)
    setError('')
    setPaused(false)
    setScanRoot(target)
    setProgress({ files: 0, folders: 0, bytes: 0, current: null, elapsed: 0 })
    try {
      const result = await api.scan(target)
      setScan(result)
      setProgress(null)
      setMessage(
        result.canceled
          ? `Scan stopped · ${count(result.files)} files read`
          : `Scanned ${count(result.files)} files · ${count(result.folders)} folders in ${result.duration.toFixed(1)}s`,
      )
      api
        .scans()
        .then((listed) => setScans(listed.scans))
        .catch(() => undefined)
    } catch (err) {
      setError((err as Error).message)
      setProgress(null)
    } finally {
      setBusy(false)
    }
  }, [])

  /** Hold the running scan, or let it continue. */
  const togglePause = useCallback(async () => {
    const next = !paused
    setPaused(next)
    try {
      if (next) await api.pauseScan()
      else await api.resumeScan()
    } catch (err) {
      setPaused(!next)
      setError((err as Error).message)
    }
  }, [paused])

  /** Stop the running scan. It stays in the index, marked incomplete. */
  const stopScan = useCallback(async () => {
    try {
      await api.cancelScan()
    } catch (err) {
      setError((err as Error).message)
    }
  }, [])

  const onSelectRoot = useCallback(
    (target: string) => {
      void runScan(target)
    },
    [runScan],
  )

  /** Open a scan that is already in the index — no new walk. */
  const onOpenScan = useCallback((meta: ScanMeta) => {
    setScan(meta)
    setError('')
    setMessage(`Scan #${meta.scan_id} · ${meta.root}`)
  }, [])

  /** Ask before removing a scan — the × is one click away from the open action. */
  const onRemoveScan = useCallback((meta: ScanMeta) => {
    setPendingRemoval(meta)
  }, [])

  const cancelRemoveScan = useCallback(() => setPendingRemoval(null), [])

  /**
   * Remove a scan from the index.
   *
   * When the open scan is the one being removed, the next stored scan takes
   * its place — the views always read from a scan that exists.
   */
  const confirmRemoveScan = useCallback(async () => {
    const meta = pendingRemoval
    if (!meta) return
    setPendingRemoval(null)
    setError('')
    try {
      await api.removeScan(meta.scan_id)
      const listed = await api.scans()
      setScans(listed.scans)
      if (scan && scan.scan_id === meta.scan_id) {
        const next = listed.scans.find((item) => item.complete) ?? listed.scans[0] ?? null
        setScan(next)
        setMessage(next ? `Scan #${next.scan_id} · ${next.root}` : 'Scan removed')
      } else {
        setMessage(`Removed scan #${meta.scan_id}`)
      }
    } catch (err) {
      setError((err as Error).message)
    }
  }, [pendingRemoval, scan])

  const tabContent = useMemo(() => {
    switch (tab) {
      case 'explore':
        return <ExploreTab scanRef={scanRef} scan={scan} scans={scans} filter={filter} />
      case 'search':
        return <SearchTab scanRef={scanRef} scan={scan} />
      case 'archives':
        return <ArchivesTab scanRef={scanRef} scan={scan} />
      case 'duplicates':
        return <DuplicatesTab scanRef={scanRef} scan={scan} />
      case 'applications':
        return <ApplicationsTab />
      case 'games':
        return <GamesTab />
      case 'monitor':
        return <MonitorTab />
      case 'snapshots':
        return <SnapshotsTab scanRef={scanRef} scan={scan} />
      case 'reports':
        return <ReportsTab scanRef={scanRef} scan={scan} />
      default:
        return null
    }
  }, [tab, scanRef, scan, scans, filter, onOpenScan])

  return (
    <div className="app">
      <header className={`app-topbar${IS_MAC ? ' mac' : ''}`}>
        <div className="brand">
          <span className="brand-mark">D</span>
          DiskGOup
        </div>

        <nav className="tabs" role="tablist" aria-label="Sections">
          {TABS.map((item) => (
            <button
              key={item.id}
              role="tab"
              aria-selected={tab === item.id}
              className="tab"
              onClick={() => setTab(item.id)}
            >
              {item.label}
            </button>
          ))}
        </nav>

        <div className="topbar-spacer" />

        {tab !== 'search' && (
          <label className="search-field">
            <span aria-hidden>⌕</span>
            <input
              value={filter}
              onChange={(event) => setFilter(event.target.value)}
              placeholder="Filter by name…"
              aria-label="Filter by name"
            />
          </label>
        )}

        <button
          className="icon-button"
          onClick={() => setFocus((value) => !value)}
          title={focus ? 'Show the side panels (Esc)' : 'Hide the side panels'}
          aria-label={focus ? 'Show the side panels' : 'Hide the side panels'}
          aria-pressed={focus}
        >
          {focus ? <CollapseIcon /> : <ExpandIcon />}
        </button>
      </header>

      {progress && (
        <div className={`scan-bar${paused ? ' paused' : ''}`} role="status">
          <span className="scan-dot" aria-hidden="true" />
          <span className="scan-state">{paused ? 'Paused' : 'Scanning'}</span>
          <span className="scan-target" title={scanRoot}>
            {shortenPath(scanRoot, 32)}
          </span>
          <span className="scan-current" title={progress.current ?? ''}>
            {progress.current ? tailPath(progress.current) : ''}
          </span>
          <span className="scan-stats">
            {count(progress.files)} files · {bytes(progress.bytes)} ·{' '}
            {duration(progress.elapsed)}
          </span>
          <button className="scan-button" onClick={() => void togglePause()}>
            {paused ? 'Resume' : 'Pause'}
          </button>
          <button
            className="scan-button danger"
            onClick={() => void stopScan()}
            title="Stop the scan. It is kept in the index, marked incomplete."
          >
            Stop
          </button>
        </div>
      )}

      <div className={`app-body${focus ? ' focus' : ''}`}>
        <Sidebar
          volumes={volumes}
          scans={scans}
          scan={scan}
          busy={busy}
          onSelectRoot={onSelectRoot}
          onOpenScan={onOpenScan}
          onRemoveScan={onRemoveScan}
        />

        <main className="workspace">{tabContent}</main>

        <Inspector scan={scan} />
      </div>

      <footer className="status-bar">
        <span className={status?.running ? 'indicator' : 'indicator offline'}>
          <span className="led" />
          {status?.running ? 'CLI connected' : 'CLI offline'}
        </span>
        <span className="spacer" />
        {error && <span className="up">{error}</span>}
        {message && <span>{message}</span>}
      </footer>

      {pendingRemoval && (
        <ConfirmDialog
          title="Remove this scan?"
          body={`${pendingRemoval.root} · ${bytes(pendingRemoval.total_size)} will be removed from the index. No files are deleted.`}
          confirmLabel="Remove scan"
          onCancel={cancelRemoveScan}
          onConfirm={() => void confirmRemoveScan()}
        />
      )}
    </div>
  )
}
