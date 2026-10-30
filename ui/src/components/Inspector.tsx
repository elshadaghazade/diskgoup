import { api } from '../lib/api'
import { baseName, bytes, count, date, duration, percent } from '../lib/format'
import type { BrowserEntry, ScanMeta } from '../lib/types'

type Props = {
  scan: ScanMeta | null
  /** The entry the user touched in the browser. */
  selected: BrowserEntry | null
}

/**
 * The right-hand inspector: details about the current scan, or about the
 * entry the user selected in the folder browser.
 */
export default function Inspector({ scan, selected }: Props) {
  if (selected && scan) {
    return (
      <aside className="inspector">
        <div className="section">
          <div className="sidebar-label">Details</div>
          <h2 title={selected.path}>{selected.name}</h2>
          <div className="selected-size">{bytes(selected.size)}</div>
          <div style={{ color: 'var(--dim)', fontSize: 12 }}>
            {selected.is_dir ? 'Folder' : selected.kind}
          </div>
        </div>

        <div className="section">
          <div className="sidebar-label">Measurements</div>
          <dl>
            <div>
              <dt>Size on disk</dt>
              <dd>{bytes(selected.on_disk)}</dd>
            </div>
            <div>
              <dt>Logical size</dt>
              <dd>{bytes(selected.size)}</dd>
            </div>
            {selected.is_dir && (
              <>
                <div>
                  <dt>Files</dt>
                  <dd>{count(selected.files)}</dd>
                </div>
                <div>
                  <dt>Subfolders</dt>
                  <dd>{count(selected.folders)}</dd>
                </div>
              </>
            )}
            <div>
              <dt>Share of scan</dt>
              <dd>{percent(selected.size, scan.total_size)}</dd>
            </div>
            <div>
              <dt>Modified</dt>
              <dd>{date(selected.mtime)}</dd>
            </div>
          </dl>
        </div>

        {selected.protected && (
          <div className="notice">
            This item is protected — it cannot be cleaned.
          </div>
        )}

        <div className="section">
          <div className="sidebar-label">Path</div>
          <div style={{ fontSize: 12, color: 'var(--dim)', overflowWrap: 'anywhere' }}>
            {selected.path}
          </div>
          <button
            className="button small"
            onClick={() => void api.openPath(selected.path)}
            style={{ marginTop: 8, alignSelf: 'flex-start' }}
          >
            Open in file manager
          </button>
        </div>
      </aside>
    )
  }

  if (!scan) {
    return (
      <aside className="inspector">
        <div className="empty-state">
          <div>Select a volume to explore.</div>
          <div className="hint">Choose a drive on the left, then scan it.</div>
        </div>
      </aside>
    )
  }

  return (
    <aside className="inspector">
      <div className="section">
        <div className="sidebar-label">Details</div>
        <h2 title={scan.root}>{baseName(scan.root)}</h2>
        <div className="selected-size">{bytes(scan.total_size)}</div>
      </div>

      <div className="section">
        <div className="sidebar-label">Measurements</div>
        <dl>
          <div>
            <dt>Size on disk</dt>
            <dd>{bytes(scan.total_on_disk)}</dd>
          </div>
          <div>
            <dt>Logical size</dt>
            <dd>{bytes(scan.total_size)}</dd>
          </div>
          <div>
            <dt>Files</dt>
            <dd>{count(scan.files)}</dd>
          </div>
          <div>
            <dt>Folders</dt>
            <dd>{count(scan.folders)}</dd>
          </div>
          <div>
            <dt>Duration</dt>
            <dd>{duration(scan.duration)}</dd>
          </div>
          <div>
            <dt>State</dt>
            <dd>{scan.complete ? 'complete' : 'partial'}</dd>
          </div>
        </dl>
      </div>

      {scan.skipped > 0 && (
        <div className="notice">
          {count(scan.skipped)} entries were skipped because they could not be read.
          The results are partial.
        </div>
      )}

      <div className="section">
        <div className="sidebar-label">Scope</div>
        <div style={{ fontSize: 12, color: 'var(--dim)', overflowWrap: 'anywhere' }}>
          {scan.root}
        </div>
        <button
          className="button small"
          onClick={() => void api.openPath(scan.root)}
          style={{ marginTop: 8, alignSelf: 'flex-start' }}
        >
          Open in file manager
        </button>
      </div>
    </aside>
  )
}
