import { useEffect, useState } from 'react'
import { api } from '../lib/api'
import { bytes, count } from '../lib/format'
import type { ArchiveListing, ScanMeta, ScanRef } from '../lib/types'

type Props = { scanRef: ScanRef | null; scan: ScanMeta | null }

/** Read-only archive browser — nothing is ever extracted. */
export default function ArchivesTab({ scanRef, scan }: Props) {
  const [archives, setArchives] = useState<string[]>([])
  const [selected, setSelected] = useState<string>('')
  const [listing, setListing] = useState<ArchiveListing | null>(null)
  const [preview, setPreview] = useState<{ text: string | null; reason: string | null } | null>(
    null,
  )
  const [error, setError] = useState('')

  useEffect(() => {
    if (!scanRef) return
    api
      .sizes(scanRef, 500)
      .then((result) => {
        const zips = result.entries
          .filter((item) => !item.is_dir && item.name.toLowerCase().endsWith('.zip'))
          .map((item) => item.path)
        setArchives(zips)
        if (zips.length && !selected) setSelected(zips[0])
      })
      .catch((err: Error) => setError(err.message))
  }, [scanRef, selected])

  useEffect(() => {
    if (!selected) return
    api
      .archives(selected)
      .then(setListing)
      .catch((err: Error) => setError(err.message))
  }, [selected])

  if (!scanRef || !scan) {
    return (
      <div className="empty-state">
        <div>Nothing scanned yet.</div>
        <div className="hint">Scan a volume before browsing its archives.</div>
      </div>
    )
  }

  return (
    <>
      <div className="workspace-heading">
        <h1>Archives</h1>
        <span className="summary">Read-only · nothing is extracted or executed</span>
      </div>

      <div className="workspace-content">
        {error && <div className="form-error">{error}</div>}

        <div className="panel">
          <h3>Archives found ({count(archives.length)})</h3>
          {archives.length === 0 ? (
            <div style={{ color: 'var(--dim)', fontSize: 13 }}>
              No ZIP archives were found in this scan.
            </div>
          ) : (
            <table className="data">
              <thead>
                <tr>
                  <th>Path</th>
                  <th className="num">Size</th>
                </tr>
              </thead>
              <tbody>
                {archives.map((path) => (
                  <tr
                    key={path}
                    onClick={() => setSelected(path)}
                    style={{
                      cursor: 'pointer',
                      background: path === selected ? 'var(--accent-soft)' : undefined,
                    }}
                  >
                    <td className="path">{path}</td>
                    <td className="num">
                      {bytes(
                        listing && listing.path === path ? listing.uncompressed : 0,
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        {listing && (
          <div className="panel">
            <h3>
              {listing.path.split('/').pop()} · {count(listing.items)} items ·{' '}
              {bytes(listing.uncompressed)} uncompressed · {bytes(listing.compressed)} compressed
            </h3>
            {listing.partial && (
              <div className="notice">Invalid names skipped; the listing is partial.</div>
            )}
            <table className="data">
              <thead>
                <tr>
                  <th>Path</th>
                  <th className="num">Uncompressed</th>
                  <th className="num">Compressed</th>
                  <th className="num">Ratio</th>
                </tr>
              </thead>
              <tbody>
                {listing.entries.map((entry) => (
                  <tr
                    key={entry.name}
                    onClick={() => {
                      if (entry.is_dir) return
                      void api
                        .archivePreview(listing.path, entry.name)
                        .then((result) =>
                          setPreview({ text: result.text, reason: result.reason }),
                        )
                    }}
                    style={{ cursor: entry.is_dir ? 'default' : 'pointer' }}
                  >
                    <td>
                      {entry.name}
                      {entry.encrypted && (
                        <span className="badge" style={{ marginLeft: 8 }}>
                          encrypted
                        </span>
                      )}
                    </td>
                    <td className="num">{bytes(entry.size)}</td>
                    <td className="num">{bytes(entry.compressed)}</td>
                    <td className="num">{(entry.ratio * 100).toFixed(0)}%</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {preview && (
          <div className="panel">
            <h3>Preview</h3>
            {preview.reason ? (
              <div className="notice">{preview.reason}</div>
            ) : (
              <pre
                style={{
                  margin: 0,
                  whiteSpace: 'pre-wrap',
                  wordBreak: 'break-word',
                  maxHeight: 320,
                  overflow: 'auto',
                  fontSize: 12,
                  color: 'var(--text)',
                }}
              >
                {preview.text}
              </pre>
            )}
          </div>
        )}
      </div>
    </>
  )
}
