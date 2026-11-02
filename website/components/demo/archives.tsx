'use client'

import { useEffect, useState } from 'react'
import { bytes, count } from './format'
import type { ArchivePreview, DemoArchive } from './types'

type Props = {
  archives: DemoArchive[]
}

/**
 * The archive browser — read-only.
 *
 * Nothing is extracted and nothing is executed: the listing and the preview
 * are read out of the file, the way the CLI reads them.
 */
export default function Archives({ archives }: Props) {
  const [selected, setSelected] = useState<string>('')
  const [preview, setPreview] = useState<{ member: string; result: ArchivePreview } | null>(null)

  // Open the biggest archive first — the one the reader is most likely to
  // want to look at.
  useEffect(() => {
    if (!selected && archives.length) setSelected(archives[0].path)
  }, [archives, selected])

  const current = archives.find((archive) => archive.path === selected) ?? null

  return (
    <>
      <div className="workspace-heading">
        <h1>Archives</h1>
        <span className="summary">Read-only · nothing is extracted or executed</span>
      </div>

      <div className="workspace-content">
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
                {archives.map((archive) => (
                  <tr
                    key={archive.path}
                    onClick={() => {
                      setSelected(archive.path)
                      setPreview(null)
                    }}
                    style={{
                      cursor: 'pointer',
                      background: archive.path === selected ? 'var(--accent-soft)' : undefined,
                    }}
                  >
                    <td className="path">{archive.path}</td>
                    <td className="num">{bytes(archive.size)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        {current && (
          <div className="panel">
            <h3>
              {current.path.split('/').pop()} · {count(current.listing.items)} items ·{' '}
              {bytes(current.listing.uncompressed)} uncompressed ·{' '}
              {bytes(current.listing.compressed)} compressed
            </h3>
            {current.listing.partial && (
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
                {current.listing.entries.map((entry) => (
                  <tr
                    key={entry.name}
                    onClick={() => {
                      if (entry.is_dir) return
                      const result = current.previews[entry.name]
                      if (result) setPreview({ member: entry.name, result })
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
            <h3>Preview — {preview.member}</h3>
            {preview.result.reason ? (
              <div className="notice">{preview.result.reason}</div>
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
                {preview.result.text}
              </pre>
            )}
            {preview.result.truncated && (
              <div className="browser-note">
                Partial preview: showing the first 64 KiB.
              </div>
            )}
          </div>
        )}
      </div>
    </>
  )
}
