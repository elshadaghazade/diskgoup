'use client'

import { useState } from 'react'
import { bytes, date, percent } from './format'
import type { Comparison, ScanMeta, Snapshot } from './types'

type Props = {
  scan: ScanMeta
  snapshots: Snapshot[]
  comparison: Comparison
}

/**
 * Size snapshots and the seven-day comparison.
 *
 * A snapshot records the size of every file kind. The growth needs a
 * snapshot taken at least seven days earlier — that is the one the sample
 * disk already has.
 */
export default function Snapshots({ scan, snapshots, comparison }: Props) {
  const [saved, setSaved] = useState<Snapshot[]>(snapshots)
  const [message, setMessage] = useState('')

  return (
    <>
      <div className="workspace-heading">
        <h1>Snapshots</h1>
        <span className="summary">Sample history of the same drive</span>
      </div>

      <div className="workspace-content">
        <div className="panel">
          <h3>Save a snapshot</h3>
          <p style={{ color: 'var(--dim)', fontSize: 12.5, marginTop: 0 }}>
            A snapshot records the size of every file kind. Growth needs a snapshot taken at
            least seven days earlier.
          </p>
          <button
            className="button primary"
            onClick={() => {
              const label = `Snapshot ${saved.length + 1}`
              const snapshot: Snapshot = {
                id: saved.length + 1,
                scan_id: scan.scan_id,
                label,
                created_at: Date.now() / 1000,
                total_size: comparison.total_current,
                total_on_disk: scan.total_on_disk,
                kinds: Object.fromEntries(
                  comparison.changes.map((change) => [change.kind, change.current]),
                ),
              }
              setSaved([snapshot, ...saved])
              setMessage(`Snapshot saved: ${snapshot.label}`)
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
          <h3>Saved snapshots ({saved.length})</h3>
          {saved.length === 0 ? (
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
                {saved.map((snapshot) => (
                  <tr key={`${snapshot.id}-${snapshot.created_at}`}>
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
