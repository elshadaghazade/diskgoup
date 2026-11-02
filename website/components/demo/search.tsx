'use client'

import { useMemo, useState } from 'react'
import { bytes, count, kindColor } from './format'
import type { BrowserEntry } from './types'

type Props = {
  /** Every entry of the scan — the rows the CLI searches. */
  entries: BrowserEntry[]
}

/** How many rows a page of results holds. */
const PER_PAGE = 200

/**
 * Parse a size such as ``100MB`` or ``2048`` into bytes.
 *
 * The same units the CLI accepts — 1024-based, so ``MB`` is a megabyte the
 * way a disk reports it.
 */
function parseSize(value: string): number | null {
  const text = value.trim().toLowerCase().replace(/ /g, '')
  const units: Record<string, number> = {
    b: 1,
    kb: 1024,
    kib: 1024,
    mb: 1024**2,
    mib: 1024**2,
    gb: 1024**3,
    gib: 1024**3,
    tb: 1024**4,
    tib: 1024**4,
  }
  for (const suffix of Object.keys(units).sort((a, b) => b.length - a.length)) {
    if (text.endsWith(suffix)) {
      const number = Number(text.slice(0, -suffix.length))
      return Number.isFinite(number) ? number * units[suffix] : null
    }
  }
  const plain = Number(text)
  return Number.isFinite(plain) ? plain : null
}

/** The start of a day, in the reader's own time zone. */
function startOfDay(value: string): number | null {
  const stamp = Date.parse(`${value}T00:00:00`)
  return Number.isFinite(stamp) ? stamp / 1000 : null
}

/** The end of a day — the day itself counts. */
function endOfDay(value: string): number | null {
  const stamp = Date.parse(`${value}T23:59:59.999`)
  return Number.isFinite(stamp) ? stamp / 1000 : null
}

/**
 * The advanced search.
 *
 * Every condition applies together, the end date and the size limits are
 * inclusive, and the results are reviewed page by page — the rules the CLI
 * applies to the same query.
 */
export default function Search({ entries }: Props) {
  const [name, setName] = useState('')
  const [inPath, setInPath] = useState('')
  const [extensions, setExtensions] = useState('')
  const [entryType, setEntryType] = useState('any')
  const [fromDate, setFromDate] = useState('')
  const [toDate, setToDate] = useState('')
  const [minSize, setMinSize] = useState('')
  const [maxSize, setMaxSize] = useState('')
  const [page, setPage] = useState(1)
  const [ran, setRan] = useState(false)
  const [error, setError] = useState('')

  /** The conditions of the last search — the query that was run. */
  const [query, setQuery] = useState<{
    name: string
    path: string
    extensions: string[]
    entryType: string
    from: number | null
    to: number | null
    min: number | null
    max: number | null
  } | null>(null)

  const run = () => {
    const parsedExtensions = extensions
      .split(',')
      .map((part) => part.trim().toLowerCase())
      .filter(Boolean)
      .map((part) => (part.startsWith('.') ? part : `.${part}`))

    const min = minSize.trim() ? parseSize(minSize) : null
    const max = maxSize.trim() ? parseSize(maxSize) : null
    const from = fromDate ? startOfDay(fromDate) : null
    const to = toDate ? endOfDay(toDate) : null

    if (minSize.trim() && min === null) {
      setError(`Invalid size: ${minSize}`)
      return
    }
    if (maxSize.trim() && max === null) {
      setError(`Invalid size: ${maxSize}`)
      return
    }
    if (fromDate && from === null) {
      setError('Enter a valid date range (YYYY-MM-DD).')
      return
    }
    if (toDate && to === null) {
      setError('Enter a valid date range (YYYY-MM-DD).')
      return
    }
    if (from !== null && to !== null && from > to) {
      setError('Enter a valid date range (YYYY-MM-DD).')
      return
    }
    if (min !== null && max !== null && min > max) {
      setError('Enter a valid size range; minimum cannot exceed maximum.')
      return
    }

    setError('')
    setQuery({
      name: name.trim().toLowerCase(),
      path: inPath.trim().toLowerCase(),
      extensions: parsedExtensions,
      entryType,
      from,
      to,
      min,
      max,
    })
    setPage(1)
    setRan(true)
  }

  /** The rows that match the query — the same filter the CLI applies. */
  const matches = useMemo(() => {
    if (!query) return []
    return entries
      .filter((entry) => {
        if (query.name && !entry.name.toLowerCase().includes(query.name)) return false
        if (query.path && !entry.path.toLowerCase().includes(query.path)) return false
        if (
          query.extensions.length &&
          !query.extensions.some((extension) => entry.name.toLowerCase().endsWith(extension))
        ) {
          return false
        }
        if (query.entryType === 'file' && entry.is_dir) return false
        if (query.entryType === 'folder' && !entry.is_dir) return false
        if (query.from !== null && entry.mtime < query.from) return false
        if (query.to !== null && entry.mtime > query.to) return false
        if (query.min !== null && entry.size < query.min) return false
        if (query.max !== null && entry.size > query.max) return false
        return true
      })
      .sort((left, right) => right.size - left.size || left.path.localeCompare(right.path))
  }, [entries, query])

  const pages = Math.max(1, Math.ceil(matches.length / PER_PAGE))
  const shown = matches.slice((page - 1) * PER_PAGE, page * PER_PAGE)

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

          <button className="button primary" onClick={run}>
            Search
          </button>
        </div>

        {ran && (
          <div className="panel">
            <h3>
              {count(matches.length)} match{matches.length === 1 ? '' : 'es'} · page {page} of{' '}
              {pages}
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
                {shown.map((match) => (
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

            {matches.length === 0 && (
              <div style={{ color: 'var(--dim)', fontSize: 13 }}>
                Nothing matches these conditions.
              </div>
            )}

            {pages > 1 && (
              <div style={{ display: 'flex', gap: 8, marginTop: 12 }}>
                <button
                  className="button small"
                  disabled={page <= 1}
                  onClick={() => setPage(page - 1)}
                >
                  Previous
                </button>
                <button
                  className="button small"
                  disabled={page >= pages}
                  onClick={() => setPage(page + 1)}
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
