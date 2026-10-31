import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { api } from '../lib/api'
import { bytes, count, kindColor, percent, baseName } from '../lib/format'
import type { BrowserEntry, BrowserFolder, ScanMeta, ScanRef } from '../lib/types'
import CleanupDialog from './CleanupDialog'

type Props = {
  scanRef: ScanRef | null
  scan: ScanMeta | null
  filter: string
  /** The entry the user last touched — the inspector shows it. */
  onSelect: (entry: BrowserEntry | null) => void
  /**
   * The scan got new totals.
   *
   * A refresh or a cleanup corrects the totals in the index, and the listing
   * carries the corrected ones — the rest of the app has to follow.
   */
  onScan: (scan: ScanMeta) => void
}

/** How many cards are drawn for one folder. */
const LIMIT = 1000

/**
 * The folder browser.
 *
 * It shows one folder of the scan at a time: the breadcrumb says where the
 * folder is, the arrow on a folder card opens it, and the up button goes one
 * level higher. Everything is read from the scan index, so opening a folder
 * never touches the disk.
 */
export default function Browser({ scanRef, scan, filter, onSelect, onScan }: Props) {
  const [folder, setFolder] = useState<BrowserFolder | null>(null)
  const [selected, setSelected] = useState<string[]>([])
  const [focused, setFocused] = useState<BrowserEntry | null>(null)
  const [anchor, setAnchor] = useState<string | null>(null)
  /** Items that were cleaned — the index still lists them until a rescan. */
  const [gone, setGone] = useState<string[]>([])
  const [error, setError] = useState('')
  const [note, setNote] = useState('')
  const [busy, setBusy] = useState(false)
  const [loading, setLoading] = useState(false)
  const [reviewing, setReviewing] = useState(false)
  /** The newest request — an older answer must not overwrite a newer one. */
  const request = useRef(0)

  const show = useCallback((result: BrowserFolder) => {
    setFolder(result)
    setSelected([])
    setFocused(null)
    setAnchor(null)
    setNote('')
  }, [])

  /** Open a folder in place. */
  const load = useCallback(
    (target: string, note?: string) => {
      if (!scanRef) return
      const id = ++request.current
      setLoading(true)
      setError('')
      api
        .browse(scanRef, target)
        .then((result) => {
          if (id !== request.current) return
          show(result)
          // The listing carries the totals the index holds now — a refresh
          // or a cleanup may have corrected them.
          onScan(result.scan)
          if (note) setNote(note)
          setLoading(false)
        })
        .catch((err: Error) => {
          if (id !== request.current) return
          setError(err.message)
          setLoading(false)
        })
    },
    [scanRef, show, onScan],
  )

  // Open the scan root whenever the scan changes.
  useEffect(() => {
    if (!scanRef) return
    setGone([])
    load(scanRef.path)
  }, [scanRef, load])

  // The inspector shows the entry the user last touched.
  useEffect(() => {
    onSelect(focused)
  }, [focused, onSelect])

  const visible = useMemo(() => {
    const needle = filter.trim().toLowerCase()
    if (!folder) return []
    return folder.entries.filter(
      (entry) =>
        !gone.includes(entry.path) &&
        (!needle || entry.name.toLowerCase().includes(needle)),
    )
  }, [folder, filter, gone])

  /**
   * What is drawn.
   *
   * A folder can hold tens of thousands of entries — a browser cache easily
   * does — and a card for every one of them would take the window down with
   * it. The first `LIMIT` of them are shown and the rest are counted, so the
   * user knows there are more. The filter still reaches all of them.
   */
  const shown = useMemo(() => visible.slice(0, LIMIT), [visible])

  /**
   * Click a card.
   *
   * A plain click selects one item, Cmd/Ctrl toggles it and Shift takes a
   * range — the same rules a file manager uses.
   */
  const onCardClick = (
    entry: BrowserEntry,
    event: { metaKey: boolean; ctrlKey: boolean; shiftKey: boolean },
  ) => {
    if (event.metaKey || event.ctrlKey) {
      setSelected((current) =>
        current.includes(entry.path)
          ? current.filter((path) => path !== entry.path)
          : [...current, entry.path],
      )
      setFocused(entry)
      setAnchor(entry.path)
      return
    }
    if (event.shiftKey && anchor) {
      const paths = shown.map((item) => item.path)
      const from = paths.indexOf(anchor)
      const to = paths.indexOf(entry.path)
      if (from >= 0 && to >= 0) {
        const [start, end] = from <= to ? [from, to] : [to, from]
        setSelected(paths.slice(start, end + 1))
        setFocused(entry)
        return
      }
    }
    setSelected([entry.path])
    setFocused(entry)
    setAnchor(entry.path)
  }

  /**
   * Stage the selection for cleanup and open the review.
   *
   * The review only opens when the selection holds something the system
   * allows — an item it protects is refused with the reason why, and the list
   * stays where it is instead of opening an empty review. An item that is
   * already in the review counts as allowed: it is there, and the review is
   * where the user can see it.
   */
  const onClean = async () => {
    if (!scanRef || selected.length === 0) return
    setBusy(true)
    setError('')
    setNote('')
    try {
      const result = await api.stageCleanup(scanRef, selected)
      if (result.refused.length > 0) {
        setError(
          `${count(result.refused.length)} item${result.refused.length > 1 ? 's' : ''} cannot be cleaned. ` +
            result.refused.map((item) => `${baseName(item.path)}: ${item.reason}`).join(' '),
        )
      }
      const refused = new Set(result.refused.map((item) => item.path))
      const allowed = selected.filter((path) => !refused.has(path))
      if (allowed.length > 0) {
        setNote(
          result.staged.length > 0
            ? 'Added to review. Nothing has been removed.'
            : 'Already in the review. Nothing has been removed.',
        )
        setReviewing(true)
      }
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setBusy(false)
    }
  }

  /**
   * Walk the folder again and correct the index.
   *
   * Only this folder is walked — the rest of the scan keeps what it holds,
   * and the totals are corrected by the difference.
   */
  const onRefresh = async () => {
    if (!scanRef || !folder) return
    setBusy(true)
    setError('')
    try {
      const result = await api.refresh(scanRef, folder.path)
      load(
        folder.path,
        `Refreshed — ${count(result.files)} file${result.files === 1 ? '' : 's'}.`,
      )
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setBusy(false)
    }
  }

  /** The items were moved to the recycle bin — the index dropped their rows. */
  const onCommitted = (moved: string[]) => {
    setGone((current) => [...current, ...moved])
    setSelected((current) => current.filter((path) => !moved.includes(path)))
    setReviewing(false)
    const note = `${count(moved.length)} item${moved.length > 1 ? 's' : ''} moved to the recycle bin.`
    if (folder) {
      // The index no longer lists what was removed — read the folder again.
      load(folder.path, note)
    } else {
      setNote(note)
    }
  }

  if (!scanRef || !scan) return null

  const crumbs = folder?.crumbs ?? []
  const isLast = (path: string) => path === folder?.path

  return (
    <>
      <div className="browser-bar">
        <nav className="breadcrumb" aria-label="Folder path">
          {crumbs.map((crumb, index) => (
            <span className="crumb" key={crumb.path}>
              {index > 0 && (
                <span className="sep" aria-hidden>
                  ›
                </span>
              )}
              <button
                className={isLast(crumb.path) ? 'current' : ''}
                onClick={() => load(crumb.path)}
                title={crumb.path}
                aria-current={isLast(crumb.path) ? 'page' : undefined}
              >
                {crumb.name}
              </button>
            </span>
          ))}
        </nav>

        <div className="view-actions">
          {loading && (
            <span className="browser-loading" role="status">
              <span className="spinner" aria-hidden="true" />
              Loading…
            </span>
          )}
          <button
            className="button small"
            onClick={() => folder?.parent && load(folder.parent)}
            disabled={loading || !folder?.parent}
            title="Open the parent folder"
          >
            ↑ Up
          </button>
          <button
            className="button small"
            onClick={() => void onRefresh()}
            disabled={loading || busy || !folder}
            title="Walk this folder again and update the index"
          >
            ↻ Refresh
          </button>
          <button
            className="button small danger"
            onClick={() => void onClean()}
            disabled={loading || selected.length === 0 || busy}
            title="Clean the selected items"
          >
            Clean
          </button>
        </div>
      </div>

      {note && <div className="browser-note">{note}</div>}
      {folder?.stale && (
        <div className="browser-note">
          This folder changed on the disk. Refresh it to bring the index up to date.
        </div>
      )}
      {error && <div className="form-error">{error}</div>}

      <div className="workspace-content">
        <div
          className={`folder-grid${loading ? ' loading' : ''}`}
          role="listbox"
          aria-multiselectable="true"
          aria-label="Folder contents"
        >
          {shown.map((entry) => {
            const isSelected = selected.includes(entry.path)
            const hasChildren = entry.files + entry.folders > 0
            return (
              <div
                key={entry.path}
                className={`folder-card${isSelected ? ' selected' : ''}`}
                role="option"
                aria-selected={isSelected}
                tabIndex={0}
                title={entry.path}
                onClick={(event) => onCardClick(entry, event)}
                onDoubleClick={() => entry.is_dir && load(entry.path)}
                onKeyDown={(event) => {
                  if (event.key === 'Enter' || event.key === ' ') {
                    event.preventDefault()
                    onCardClick(entry, event)
                  }
                }}
              >
                <span className="glyph" style={{ color: kindColor(entry.kind) }} aria-hidden>
                  {entry.is_dir ? '▤' : '▪'}
                </span>
                <span className="name">{entry.name}</span>
                {(entry.protected || entry.critical) && (
                  <span className="flags">
                    {entry.critical && (
                      <span
                        className="badge critical"
                        title="This folder is required by the system or your account — it cannot be cleaned."
                      >
                        system
                      </span>
                    )}
                    {entry.protected && !entry.critical && (
                      <span
                        className="badge protected"
                        title="Protected — this item cannot be cleaned."
                      >
                        protected
                      </span>
                    )}
                  </span>
                )}
                <span className="meta">
                  {entry.is_dir && <span className="items">{count(entry.files)} files</span>}
                  <span className="size">{bytes(entry.size)}</span>
                  {!entry.is_dir && <span>{percent(entry.size, scan.total_size, 0)}</span>}
                </span>
                {entry.is_dir && hasChildren && (
                  <button
                    className="open"
                    aria-label={`Open ${entry.name}`}
                    title="Open this folder"
                    onClick={(event) => {
                      event.stopPropagation()
                      load(entry.path)
                    }}
                  >
                    ›
                  </button>
                )}
              </div>
            )
          })}
        </div>

        {visible.length > shown.length && (
          <div className="browser-note">
            Showing the first {count(shown.length)} of {count(visible.length)} entries. Narrow
            the list with the filter above to reach the rest.
          </div>
        )}

        {visible.length === 0 && (
          <div className="empty-state">
            <div>
              {loading
                ? 'Loading the folder…'
                : filter
                  ? 'No entries match this filter.'
                  : 'This folder is empty.'}
            </div>
          </div>
        )}
      </div>

      {reviewing && (
        <CleanupDialog
          scanRef={scanRef}
          onClose={() => setReviewing(false)}
          onCommitted={onCommitted}
        />
      )}
    </>
  )
}
