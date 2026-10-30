import { useState } from 'react'
import { api } from '../lib/api'
import { bytes, count } from '../lib/format'
import type { DuplicateResponse, ScanMeta, ScanRef } from '../lib/types'

type Props = { scanRef: ScanRef | null; scan: ScanMeta | null }

/** Duplicate groups — content verified with SHA-256 and an exact byte compare. */
export default function DuplicatesTab({ scanRef, scan }: Props) {
  const [result, setResult] = useState<DuplicateResponse | null>(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  async function run() {
    if (!scanRef) return
    setBusy(true)
    setError('')
    try {
      setResult(await api.duplicates(scanRef))
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setBusy(false)
    }
  }

  if (!scanRef || !scan) {
    return (
      <div className="empty-state">
        <div>Nothing scanned yet.</div>
        <div className="hint">Scan a volume before looking for duplicates.</div>
      </div>
    )
  }

  return (
    <>
      <div className="workspace-heading">
        <h1>Duplicates</h1>
        <span className="summary">Same content. Extra space.</span>
      </div>

      <div className="workspace-content">
        {error && <div className="form-error">{error}</div>}

        <div className="panel">
          <h3>Find duplicates</h3>
          <p style={{ color: 'var(--dim)', fontSize: 12.5, marginTop: 0 }}>
            Content is verified with SHA-256 and an exact byte comparison. Equal names or
            sizes alone are never treated as proof. Zero-byte files and hard links to the
            same file are excluded.
          </p>
          <button className="button primary" onClick={() => void run()} disabled={busy}>
            {busy ? 'Scanning…' : 'Find duplicates'}
          </button>
        </div>

        {result && (
          <>
            <div className="stat-row">
              <div className="stat">
                <div className="label">Groups</div>
                <div className="value">{count(result.group_count)}</div>
              </div>
              <div className="stat">
                <div className="label">Reclaimable</div>
                <div className="value">{bytes(result.total_reclaimable)}</div>
              </div>
              <div className="stat">
                <div className="label">Candidates</div>
                <div className="value">{count(result.candidates)}</div>
              </div>
            </div>

            <div className="panel">
              <table className="data">
                <thead>
                  <tr>
                    <th className="num">Copies</th>
                    <th className="num">Size</th>
                    <th className="num">Reclaimable</th>
                    <th>Paths</th>
                  </tr>
                </thead>
                <tbody>
                  {result.groups.map((group) => (
                    <tr key={group.sha256}>
                      <td className="num">{group.copies}</td>
                      <td className="num">{bytes(group.size)}</td>
                      <td className="num">{bytes(group.reclaimable)}</td>
                      <td className="path">
                        {group.paths.map((path, index) => (
                          <div key={path}>
                            {index === 0 ? 'keep  ' : 'extra '}
                            {path}
                          </div>
                        ))}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {result.groups.length === 0 && (
                <div style={{ color: 'var(--dim)', fontSize: 13 }}>
                  No duplicates remain in the sample data.
                </div>
              )}
            </div>
          </>
        )}
      </div>
    </>
  )
}
