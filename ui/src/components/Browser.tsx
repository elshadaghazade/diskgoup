import { useCallback, useEffect, useMemo, useState } from 'react'
import { api } from '../lib/api'
import { bytes, count, kindColor, percent } from '../lib/format'
import type { BrowserEntry, BrowserFolder, ScanMeta, ScanRef } from '../lib/types'
import CleanupDialog from './CleanupDialog'

type Props = {
  scanRef: ScanRef | null
  scan: ScanMeta | null
  filter: string
  /** The entry the user last touched — the inspector shows it. */
  onSelect: (entry: BrowserEntry | null) => void
}

/**
 * The folder browser.
 *
 * It shows one folder of the scan at a time: the breadcrumb says where the
 * folder is, the arrow on a folder card opens it, and the up button goes one
 * level higher. Everything is read from the scan index, so opening a folder
 * never touches the disk.
 */
export default function Browser({ scanRef, scan, filter, onSelect }: Props) {
  const [folder, setFolder] = useState<BrowserFolder | null>(null)
  const [selected, setSelected] = useState<string[]>([])
  const [focused, setFocused] = useState<BrowserEntry | null>(null)
  const [anchor, setAnchor] = useState<string | null>(null)
  /** Items that were cleaned — the index still lists them until a rescan. */
  const [gone, setGone] = useState<string[]>([])
  const [error, setError] = useState('')
  const [note, setNote] = useState('')
  const [busy, setBusy] = useState(false)
  const [reviewing, setReviewing] = useState(false)

  const show = useCallback(
    (result: BrowserFolder) => {
      setFolder(result)
      setSelected([])
      setFocused(null)
      setAnchor(null)
      setGone([])
      setNote('')
    },
    [],
  )

  // Open the scan root whenever the scan changes.
  useEffect(() => {
    if (!scanRef) return
    let cancelled = false
    api
      .browse(scanRef, scanRef.path)
      .then((result) => {
        if (!cancelled) show(result)
      })
      .catch((err: Error) => !cancelled && setError(err.message))
    return () => {
      cancelled = true
    }
  }, [scanRef, show])

  // The inspector shows the entry the user last touched.
  useEffect(() => {
    onSelect(focused)
  }, [focused, onSelect])

  /** Open a folder in place. */
  const open = useCallback(
    (target: string) => {
      if (!scanRef) return
      setError('')
      api
        .browse(scanRef, target)
        .then(show)
        .catch((err: Error) => setError(err.message))
    },
    [scanRef, show],
  )

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
      const paths = visible.map((item) => item.path)
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

  /** Stage the selection for cleanup and open the review. */
  const onClean = async () => {
    if (!scanRef || selected.length === 0) return
    setBusy(true)
    setError('')
    setNote('')
    try {
      const result = await api.stageCleanup(scanRef, selected)
      if (result.refused.length > 0) {
        setError(
          `${result.refused.length} item${result.refused.length > 1 ? 's' : ''} cannot be cleaned. ` +
            result.refused.map((item) => item.reason).join(' '),
        )
      }
      setReviewing(true)
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setBusy(false)
    }
  }

  /** The items were moved to the recycle bin — take them off the screen. */
  const onCommitted = (moved: string[]) => {
    setGone((current) => [...current, ...moved])
    setSelected((current) => current.filter((path) => !moved.includes(path)))
    setReviewing(false)
    setNote(
      `${count(moved.length)} item${moved.length > 1 ? 's' : ''} moved to the recycle bin. ` +
        'The scan still lists them until it is refreshed.',
    )
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
                onClick={() => open(crumb.path)}
                title={crumb.path}
                aria-current={isLast(crumb.path) ? 'page' : undefined}
              >
                {crumb.name}
              </button>
            </span>
          ))}
        </nav>

        <div className="view-actions">
          <button
            className="button small"
            onClick={() => folder?.parent && open(folder.parent)}
            disabled={!folder?.parent}
            title="Open the parent folder"
          >
            ↑ Up
          </button>
          <button
            className="button small danger"
            onClick={() => void onClean()}
            disabled={selected.length === 0 || busy}
            title="Clean the selected items"
          >
            Clean
          </button>
        </div>
      </div>

      {note && <div className="browser-note">{note}</div>}
      {error && <div className="form-error">{error}</div>}

      <div className="workspace-content">
        <div
          className="folder-grid"
          role="listbox"
          aria-multiselectable="true"
          aria-label="Folder contents"
        >
          {visible.map((entry) => {
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
                onDoubleClick={() => entry.is_dir && open(entry.path)}
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
                      open(entry.path)
                    }}
                  >
                    ›
                  </button>
                )}
              </div>
            )
          })}
        </div>

        {visible.length === 0 && (
          <div className="empty-state">
            <div>{filter ? 'No entries match this filter.' : 'This folder is empty.'}</div>
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
