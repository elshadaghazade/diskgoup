import { useEffect, useState } from 'react'
import { api } from '../lib/api'
import { bytes, date, percent } from '../lib/format'
import type { Comparison, ScanMeta, ScanRef, Snapshot } from '../lib/types'

type Props = { scanRef: ScanRef | null; scan: ScanMeta | null }

/** Size snapshots and the seven-day comparison. */
export default function SnapshotsTab({ scanRef, scan }: Props) {
  const [snapshots, setSnapshots] = useState<Snapshot[]>([])
  const [comparison, setComparison] = useState<Comparison | null>(null)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')

  useEffect(() => {
    if (!scanRef) return
    api
      .snapshots(scanRef)
      .then((result) => setSnapshots(result.snapshots))
      .catch((err: Error) => setError(err.message))
    api
      .compareSnapshots(scanRef)
      .then(setComparison)
      .catch(() => setComparison(null))
  }, [scanRef])

  if (!scanRef || !scan) {
    return (
      <div className="empty-state">
        <div>Nothing scanned yet.</div>
        <div className="hint">Scan a volume before taking snapshots.</div>
      </div>
    )
  }

  return (
    <>
      <div className="workspace-heading">
        <h1>Snapshots</h1>
        <span className="summary">Sample history of the same drive</span>
      </div>

      <div className="workspace-content">
        {error && <div className="form-error">{error}</div>}

        <div className="panel">
          <h3>Save a snapshot</h3>
          <p style={{ color: 'var(--dim)', fontSize: 12.5, marginTop: 0 }}>
            A snapshot records the size of every file kind. Growth needs a snapshot taken
            at least seven days earlier.
          </p>
          <button
            className="button primary"
            onClick={() => {
              void api
                .saveSnapshot(scanRef, `Snapshot ${snapshots.length + 1}`)
                .then((snapshot) => {
                  setSnapshots((current) => [snapshot, ...current])
                  setMessage(`Snapshot saved: ${snapshot.label}`)
                })
                .catch((err: Error) => setError(err.message))
            }}
          >
            Save snapshot
          </button>
        </div>

        {comparison && !comparison.has_history && (
          <div className="notice">
            No comparable history. Growth requires a file-type report for the same drive at
            least 7 days earlier. Current usage is shown below.
          </div>
        )}

        {comparison?.has_history && (
          <div className="stat-row">
            <div className="stat">
              <div className="label">Current</div>
              <div className="value">{bytes(comparison.total_current)}</div>
            </div>
            <div className="stat">
              <div className="label">7-day change</div>
              <div
                className={`value ${comparison.total_growth > 0 ? 'up' : comparison.total_growth < 0 ? 'down' : ''}`}
              >
                {comparison.total_growth >= 0 ? '+' : '−'}
                {bytes(Math.abs(comparison.total_growth))}
              </div>
              <div className="note">
                {percent(Math.abs(comparison.total_growth), comparison.total_baseline ?? 1)}
              </div>
            </div>
          </div>
        )}

        {comparison && (
          <div className="panel">
            <h3>Usage of all file types</h3>
            <table className="data">
              <thead>
                <tr>
                  <th>Type</th>
                  <th className="num">Current</th>
                  <th className="num">Growth</th>
                  <th className="num">Usage share</th>
                </tr>
              </thead>
              <tbody>
                {comparison.changes.map((change) => (
                  <tr key={change.kind}>
                    <td>{change.kind}</td>
                    <td className="num">{bytes(change.current)}</td>
                    <td
                      className={`num ${change.growth > 0 ? 'up' : change.growth < 0 ? 'down' : ''}`}
                    >
                      {comparison.has_history
                        ? `${change.growth >= 0 ? '+' : '−'}${bytes(Math.abs(change.growth))}`
                        : '—'}
                    </td>
                    <td className="num">{percent(change.current, comparison.total_current)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        <div className="panel">
          <h3>Saved snapshots ({snapshots.length})</h3>
          {snapshots.length === 0 ? (
            <div style={{ color: 'var(--dim)', fontSize: 13 }}>No snapshots yet.</div>
          ) : (
            <table className="data">
              <thead>
                <tr>
                  <th>Label</th>
                  <th className="num">Total</th>
                  <th>Taken</th>
                </tr>
              </thead>
              <tbody>
                {snapshots.map((snapshot) => (
                  <tr key={snapshot.id}>
                    <td>{snapshot.label}</td>
                    <td className="num">{bytes(snapshot.total_size)}</td>
                    <td style={{ color: 'var(--dim)' }}>{date(snapshot.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        {message && <div className="notice">{message}</div>}
      </div>
    </>
  )
}
