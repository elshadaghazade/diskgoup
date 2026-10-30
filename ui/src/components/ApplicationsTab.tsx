import { useEffect, useState } from 'react'
import { api } from '../lib/api'
import { bytes, count } from '../lib/format'
import type { Application } from '../lib/types'

/** The installed applications and the space they occupy. */
export default function ApplicationsTab() {
  const [applications, setApplications] = useState<Application[]>([])
  const [total, setTotal] = useState(0)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api
      .apps()
      .then((result) => {
        setApplications(result.applications)
        setTotal(result.total_size)
      })
      .catch((err: Error) => setError(err.message))
      .finally(() => setLoading(false))
  }, [])

  return (
    <>
      <div className="workspace-heading">
        <h1>Applications</h1>
        <span className="summary">Applications and their footprint.</span>
      </div>

      <div className="workspace-content">
        {error && <div className="form-error">{error}</div>}
        {loading && <div style={{ color: 'var(--dim)' }}>Reading the application inventory…</div>}

        {!loading && applications.length > 0 && (
          <>
            <div className="stat-row">
              <div className="stat">
                <div className="label">Applications</div>
                <div className="value">{count(applications.length)}</div>
              </div>
              <div className="stat">
                <div className="label">Total size</div>
                <div className="value">{bytes(total)}</div>
              </div>
            </div>

            <div className="panel">
              <table className="data">
                <thead>
                  <tr>
                    <th>Name</th>
                    <th>Version</th>
                    <th className="num">Size</th>
                    <th>Location</th>
                  </tr>
                </thead>
                <tbody>
                  {applications.map((application) => (
                    <tr key={application.id}>
                      <td>{application.name}</td>
                      <td style={{ color: 'var(--dim)' }}>{application.version ?? '—'}</td>
                      <td className="num">{bytes(application.size)}</td>
                      <td className="path">{application.path ?? '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}

        {!loading && applications.length === 0 && (
          <div className="empty-state">
            <div>No applications were found on this machine.</div>
          </div>
        )}
      </div>
    </>
  )
}
