import { useState } from 'react'
import { api } from '../lib/api'
import { date } from '../lib/format'
import type { ScanMeta, ScanRef } from '../lib/types'

type Props = { scanRef: ScanRef | null; scan: ScanMeta | null }

/** Weekly HTML report and the file-type CSV export. */
export default function ReportsTab({ scanRef, scan }: Props) {
  const [html, setHtml] = useState<string>('')
  const [csv, setCsv] = useState<string>('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  if (!scanRef || !scan) {
    return (
      <div className="empty-state">
        <div>Nothing scanned yet.</div>
        <div className="hint">Scan a volume before generating a report.</div>
      </div>
    )
  }

  return (
    <>
      <div className="workspace-heading">
        <h1>Reports</h1>
        <span className="summary">Why is the disk full?</span>
      </div>

      <div className="workspace-content">
        {error && <div className="form-error">{error}</div>}

        <div className="panel">
          <h3>Weekly report</h3>
          <p style={{ color: 'var(--dim)', fontSize: 12.5, marginTop: 0 }}>
            A self-contained HTML report with the file-type breakdown, the growth since the
            baseline snapshot and the largest folders. Generated locally — no data leaves
            this machine.
          </p>
          <button
            className="button primary"
            disabled={busy}
            onClick={() => {
              setBusy(true)
              setError('')
              api
                .weeklyReport(scanRef)
                .then((result) => setHtml(result.html))
                .catch((err: Error) => setError(err.message))
                .finally(() => setBusy(false))
            }}
          >
            {busy ? 'Generating…' : 'Generate weekly report'}
          </button>
        </div>

        {html && (
          <div className="panel">
            <h3>Preview</h3>
            <iframe
              title="Weekly report"
              srcDoc={html}
              style={{
                width: '100%',
                height: 520,
                border: '1px solid var(--border)',
                borderRadius: 8,
                background: '#0d1117',
              }}
            />
          </div>
        )}

        <div className="panel">
          <h3>File-type report (CSV)</h3>
          <p style={{ color: 'var(--dim)', fontSize: 12.5, marginTop: 0 }}>
            The per-type size and share of the scanned bytes, as CSV.
          </p>
          <button
            className="button"
            disabled={busy}
            onClick={() => {
              setBusy(true)
              setError('')
              api
                .typesReport(scanRef)
                .then((result) => setCsv(result.csv))
                .catch((err: Error) => setError(err.message))
                .finally(() => setBusy(false))
            }}
          >
            Generate CSV report
          </button>
        </div>

        {csv && (
          <div className="panel">
            <h3>CSV</h3>
            <pre
              style={{
                margin: 0,
                fontSize: 12,
                overflow: 'auto',
                maxHeight: 280,
                color: 'var(--text)',
              }}
            >
              {csv}
            </pre>
            <button
              className="button small"
              style={{ marginTop: 10 }}
              onClick={() => {
                const blob = new Blob([csv], { type: 'text/csv' })
                const url = URL.createObjectURL(blob)
                const link = document.createElement('a')
                link.href = url
                link.download = 'diskgoup-file-types.csv'
                link.click()
                URL.revokeObjectURL(url)
              }}
            >
              Download CSV
            </button>
          </div>
        )}

        <div className="notice">
          Measured from a scan taken {date(scan.started_at)}. Files inside cache and log
          folders count only in that group, so nothing is counted twice.
        </div>
      </div>
    </>
  )
}
