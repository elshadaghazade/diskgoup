'use client'

import { useCallback, useEffect, useMemo, useState } from 'react'
import { bytes, count, kindColor, percent } from './format'
import Review from './review'
import type { BrowserEntry, BrowserFolder, ScanMeta } from './types'

type Props = {
  scan: ScanMeta
  /** Every folder of the sample disk, keyed by its path. */
  folders: Record<string, BrowserFolder>
  /** The cache folders of the scan — the space the system regenerates. */
  reclaimable: BrowserFolder
  filter: string
  onSelect: (entry: BrowserEntry | null) => void
}

/** How many cards are drawn for one folder. */
const LIMIT = 400

/**
 * The folder browser.
 *
 * It shows one folder of the scan at a time: the breadcrumb says where the
 * folder is, the arrow on a folder card opens it, and the up button goes one
 * level higher.
 */
export default function Browser({ scan, folders, reclaimable, filter, onSelect }: Props) {
  const [folder, setFolder] = useState<BrowserFolder | null>(null)
  const [selected, setSelected] = useState<string[]>([])
  const [focused, setFocused] = useState<BrowserEntry | null>(null)
  const [anchor, setAnchor] = useState<string | null>(null)
  const [scope, setScope] = useState(false)
  const [note, setNote] = useState('')
  const [staged, setStaged] = useState<BrowserEntry[] | null>(null)

  const load = useCallback(
    (path: string) => {
      const next = folders[path]
      if (!next) return
      setFolder(next)
      setSelected([])
      setFocused(null)
      setAnchor(null)
      setScope(false)
      setNote('')
    },
    [folders],
  )

  // Open the scan root when the browser mounts — the same thing the
  // desktop app does whenever the scan changes.
  useEffect(() => {
    load(scan.root)
  }, [load, scan.root])

  const loadScope = useCallback(() => {
    setFolder(reclaimable)
    setSelected([])
    setFocused(null)
    setAnchor(null)
    setScope(true)
    setNote('The cache folders of this scan — the space the system regenerates. Pick what to clean.')
  }, [reclaimable])

  const visible = useMemo(() => {
    const needle = filter.trim().toLowerCase()
    if (!folder) return []
    return folder.entries.filter(
      (entry) => !needle || entry.name.toLowerCase().includes(needle),
    )
  }, [folder, filter])

  const shown = useMemo(() => visible.slice(0, LIMIT), [visible])

  const entries = useMemo(
    () => (folder ? folder.entries.filter((entry) => selected.includes(entry.path)) : []),
    [folder, selected],
  )

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

  const crumbs = folder?.crumbs ?? []
  const isLast = (path: string) => path === folder?.path

  // The inspector shows the entry the user last touched.
  useEffect(() => {
    onSelect(focused)
  }, [focused, onSelect])

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
          {scope ? (
            <>
              <button className="button small" onClick={() => load(scan.root)} title="Back to the scan">
                ← Back
              </button>
              <button
                className="button small"
                onClick={() => setSelected(shown.map((entry) => entry.path))}
                disabled={shown.length === 0}
                title="Take everything on the list"
              >
                Select all
              </button>
            </>
          ) : (
            <>
              <button
                className="button small"
                onClick={() => folder?.parent && load(folder.parent)}
                disabled={!folder?.parent}
                title="Open the parent folder"
              >
                ↑ Up
              </button>
              <button
                className="button small"
                onClick={loadScope}
                title="The cache folders of this scan — the space the system regenerates"
              >
                ✨ Safe to clean
              </button>
            </>
          )}
          <button
            className="button small danger"
            onClick={() => setStaged(entries)}
            disabled={selected.length === 0}
            title="Put the selected items on the review list"
          >
            Clean
          </button>
        </div>
      </div>

      {note && <div className="browser-note">{note}</div>}

      <div className="workspace-content">
        <div
          className="folder-grid"
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
                title={entry.reason ? `${entry.path} — ${entry.reason}` : entry.path}
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
                      <span className="badge protected" title="Protected — this item cannot be cleaned.">
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
            Showing the first {count(shown.length)} of {count(visible.length)} entries. Narrow the
            list with the filter above to reach the rest.
          </div>
        )}

        {visible.length === 0 && (
          <div className="empty-state">
            <div>{filter ? 'No entries match this filter.' : 'This folder is empty.'}</div>
          </div>
        )}
      </div>

      {staged && (
        <Review
          items={staged}
          onClose={() => setStaged(null)}
          onConfirm={() => {
            const total = staged.reduce((sum, entry) => sum + entry.size, 0)
            setStaged(null)
            setNote(
              `In the desktop app this would free ${bytes(total)} — to the recycle bin, after you approve it.`,
            )
          }}
        />
      )}
    </>
  )
}
