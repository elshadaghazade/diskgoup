import { useState } from 'react'
import { api } from '../lib/api'
import { bytes, count, kindColor } from '../lib/format'
import type { ScanMeta, ScanRef, SearchResponse } from '../lib/types'

type Props = { scanRef: ScanRef | null; scan: ScanMeta | null }

/** Advanced search — every condition applies together. */
export default function SearchTab({ scanRef, scan }: Props) {
  const [name, setName] = useState('')
  const [inPath, setInPath] = useState('')
  const [extensions, setExtensions] = useState('')
  const [entryType, setEntryType] = useState('any')
  const [fromDate, setFromDate] = useState('')
  const [toDate, setToDate] = useState('')
  const [minSize, setMinSize] = useState('')
  const [maxSize, setMaxSize] = useState('')
  const [page, setPage] = useState(1)
  const [result, setResult] = useState<SearchResponse | null>(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  async function run() {
    if (!scanRef) return
    setBusy(true)
    setError('')
    try {
      const response = await api.search(scanRef, {
        name: name || undefined,
        path_filter: inPath || undefined,
        extensions: extensions
          ? extensions
              .split(',')
              .map((part) => part.trim())
              .filter(Boolean)
          : undefined,
        entry_type: entryType,
        from_date: fromDate || undefined,
        to_date: toDate || undefined,
        min_size: minSize || undefined,
        max_size: maxSize || undefined,
        page,
        per_page: 200,
      })
      setResult(response)
    } catch (err) {
      setError((err as Error).message)
      setResult(null)
    } finally {
      setBusy(false)
    }
  }

  if (!scanRef || !scan) {
    return (
      <div className="empty-state">
        <div>Nothing scanned yet.</div>
        <div className="hint">Scan a volume before searching it.</div>
      </div>
    )
  }

  return (
    <>
      <div className="workspace-heading">
        <h1>Search</h1>
        <span className="summary">All conditions apply together · limits are inclusive</span>
      </div>

      <div className="workspace-content">
        <div className="panel">
          <h3>Conditions</h3>
          {error && <div className="form-error">{error}</div>}
          <div className="field-row">
            <div className="field">
              <label htmlFor="s-name">Name</label>
              <input
                id="s-name"
                value={name}
                onChange={(event) => setName(event.target.value)}
                placeholder="archive, .mp4, Work"
              />
            </div>
            <div className="field">
              <label htmlFor="s-path">In path</label>
              <input
                id="s-path"
                value={inPath}
                onChange={(event) => setInPath(event.target.value)}
                placeholder="a fragment of the path"
              />
            </div>
            <div className="field">
              <label htmlFor="s-ext">Extensions</label>
              <input
                id="s-ext"
                value={extensions}
                onChange={(event) => setExtensions(event.target.value)}
                placeholder="mp4, zip"
              />
            </div>
            <div className="field">
              <label htmlFor="s-type">Entry type</label>
              <select
                id="s-type"
                value={entryType}
                onChange={(event) => setEntryType(event.target.value)}
              >
                <option value="any">Any</option>
                <option value="file">Files only</option>
                <option value="folder">Folders only</option>
              </select>
            </div>
          </div>

          <div className="field-row">
            <div className="field">
              <label htmlFor="s-from">From date</label>
              <input
                id="s-from"
                type="date"
                value={fromDate}
                onChange={(event) => setFromDate(event.target.value)}
              />
            </div>
            <div className="field">
              <label htmlFor="s-to">To date</label>
              <input
                id="s-to"
                type="date"
                value={toDate}
                onChange={(event) => setToDate(event.target.value)}
              />
            </div>
            <div className="field">
              <label htmlFor="s-min">Minimum size</label>
              <input
                id="s-min"
                value={minSize}
                onChange={(event) => setMinSize(event.target.value)}
                placeholder="100MB"
              />
            </div>
            <div className="field">
              <label htmlFor="s-max">Maximum size</label>
              <input
                id="s-max"
                value={maxSize}
                onChange={(event) => setMaxSize(event.target.value)}
                placeholder="2GB"
              />
            </div>
          </div>

          <button className="button primary" onClick={() => void run()} disabled={busy}>
            {busy ? 'Searching…' : 'Search'}
          </button>
        </div>

        {result && (
          <div className="panel">
            <h3>
              {count(result.total)} matches · page {result.page} of {result.pages}
            </h3>
            <table className="data">
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Path</th>
                  <th className="num">Size</th>
                </tr>
              </thead>
              <tbody>
                {result.matches.map((match) => (
                  <tr key={match.path}>
                    <td>
                      <span className="kind-dot" style={{ background: kindColor(match.kind) }} />
                      {match.name}
                    </td>
                    <td className="path">{match.path}</td>
                    <td className="num">{bytes(match.size)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {result.pages > 1 && (
              <div style={{ display: 'flex', gap: 8, marginTop: 12 }}>
                <button
                  className="button small"
                  disabled={page <= 1}
                  onClick={() => {
                    setPage(page - 1)
                    window.setTimeout(() => void run(), 0)
                  }}
                >
                  Previous
                </button>
                <button
                  className="button small"
                  disabled={page >= result.pages}
                  onClick={() => {
                    setPage(page + 1)
                    window.setTimeout(() => void run(), 0)
                  }}
                >
                  Next
                </button>
              </div>
            )}
          </div>
        )}
      </div>
    </>
  )
}
