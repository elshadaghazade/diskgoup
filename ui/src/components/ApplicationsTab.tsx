import { useEffect, useState } from 'react'
import { api } from '../lib/api'
import { bytes, count } from '../lib/format'
import type { Application } from '../lib/types'
import ConfirmDialog from './ConfirmDialog'

/** The installed applications and the space they occupy. */
export default function ApplicationsTab() {
  const [applications, setApplications] = useState<Application[]>([])
  const [total, setTotal] = useState(0)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [loading, setLoading] = useState(true)
  const [asking, setAsking] = useState<Application | null>(null)
  const [confirming, setConfirming] = useState(false)
  const [busy, setBusy] = useState(false)

  const load = () =>
    api.apps().then((result) => {
      setApplications(result.applications)
      setTotal(result.total_size)
    })

  useEffect(() => {
    load()
      .catch((err: Error) => setError(err.message))
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => {
    if (!asking) return
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape' && !busy) setAsking(null)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [asking, busy])

  /** Remove the application and read the inventory again. */
  const remove = async (permanent: boolean) => {
    if (!asking) return
    setBusy(true)
    setError('')
    try {
      const result = await api.appsUninstall(asking.id, permanent)
      if (!result.ok) {
        setError(result.message)
        return
      }
      setNotice(result.message)
      setAsking(null)
      setConfirming(false)
      await load()
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <>
      <div className="workspace-heading">
        <h1>Applications</h1>
        <span className="summary">Applications and their footprint.</span>
      </div>

      <div className="workspace-content">
        {error && <div className="form-error">{error}</div>}
        {notice && !error && <div className="notice">{notice}</div>}
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
                    <th />
                  </tr>
                </thead>
                <tbody>
                  {applications.map((application) => (
                    <tr key={application.id}>
                      <td>
                        {application.name}
                        {application.protected && (
                          <span className="badge protected" style={{ marginLeft: 8 }}>
                            system
                          </span>
                        )}
                      </td>
                      <td style={{ color: 'var(--dim)' }}>{application.version ?? '—'}</td>
                      <td className="num">{bytes(application.size)}</td>
                      <td className="path">{application.path ?? '—'}</td>
                      <td>
                        <button
                          className="button danger"
                          onClick={() => {
                            setError('')
                            setAsking(application)
                          }}
                          disabled={application.protected || busy}
                          title={
                            application.protected
                              ? (application.reason ?? 'This application cannot be removed.')
                              : 'Remove this application'
                          }
                        >
                          Remove
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="notice">
              Removing an application takes away the program. Its own data — settings,
              documents, saved games — is left where it is.
            </div>
          </>
        )}

        {!loading && applications.length === 0 && (
          <div className="empty-state">
            <div>No applications were found on this machine.</div>
          </div>
        )}
      </div>

      {asking && (
        <div className="modal-backdrop" onClick={() => !busy && setAsking(null)}>
          <div
            className="modal"
            role="dialog"
            aria-modal="true"
            aria-label={`Remove ${asking.name}`}
            onClick={(event) => event.stopPropagation()}
          >
            <h2 className="modal-title">Remove {asking.name}?</h2>
            <div className="modal-body">
              <p>
                {asking.path} · {bytes(asking.size)}
              </p>
              <p>
                Moving it to the Trash keeps it recoverable — the space comes back when the
                Trash is emptied. The data of the application is left where it is.
              </p>
            </div>
            <div className="modal-actions">
              <button className="button" onClick={() => setAsking(null)} autoFocus disabled={busy}>
                Cancel
              </button>
              <button
                className="button primary"
                onClick={() => void remove(false)}
                disabled={busy}
                title="Move to the Trash — recoverable"
              >
                Move to Trash
              </button>
              <button
                className="button danger"
                onClick={() => setConfirming(true)}
                disabled={busy}
                title="Delete for good — nothing goes to the Trash"
              >
                Delete permanently
              </button>
            </div>
          </div>
        </div>
      )}

      {asking && confirming && (
        <ConfirmDialog
          title="Delete for good?"
          body={`${asking.name} (${bytes(asking.size)}) will be deleted. It does not go to the Trash and cannot be brought back.`}
          confirmLabel="Delete for good"
          onConfirm={() => void remove(true)}
          onCancel={() => setConfirming(false)}
        />
      )}
    </>
  )
}
