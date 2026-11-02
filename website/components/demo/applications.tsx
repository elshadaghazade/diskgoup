'use client'

import { useState } from 'react'
import { bytes, count, tailPath } from './format'
import type { Application } from './types'

type Props = {
  applications: Application[]
  total: number
}

/**
 * The application inventory.
 *
 * The desktop app removes an application with the uninstaller the system
 * registered for it. Here the inventory is the sample machine's — nothing is
 * removed, and the buttons say so.
 */
export default function Applications({ applications, total }: Props) {
  const [asking, setAsking] = useState<Application | null>(null)
  const [confirming, setConfirming] = useState(false)
  const [notice, setNotice] = useState('')

  return (
    <>
      <div className="workspace-heading">
        <h1>Applications</h1>
        <span className="summary">Applications and their footprint.</span>
      </div>

      <div className="workspace-content">
        {notice && <div className="notice">{notice}</div>}

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
                  <td className="path" title={application.path ?? undefined}>
                    {application.path ? tailPath(application.path, 2) : '—'}
                  </td>
                  <td>
                    <button
                      className="button danger"
                      onClick={() => {
                        setNotice('')
                        setAsking(application)
                      }}
                      disabled={application.protected}
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
          Removing an application takes away the program. Its own data — settings, documents,
          saved games — is left where it is.
        </div>
      </div>

      {asking && !confirming && (
        <div className="modal-backdrop" onClick={() => setAsking(null)}>
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
              <p style={{ color: 'var(--dim)', fontSize: 12.5 }}>
                On your own machine the registered uninstaller of the application runs here.
                This is the sample machine's inventory — nothing is removed.
              </p>
            </div>
            <div className="modal-actions">
              <button className="button" onClick={() => setAsking(null)} autoFocus>
                Cancel
              </button>
              <button
                className="button primary"
                onClick={() => {
                  setNotice(
                    `On your own machine ${asking.name} would be moved to the Trash — the space comes back when the Trash is emptied.`,
                  )
                  setAsking(null)
                }}
                title="Move to the Trash — recoverable"
              >
                Move to Trash
              </button>
              <button
                className="button danger"
                onClick={() => setConfirming(true)}
                title="Delete for good — nothing goes to the Trash"
              >
                Delete permanently
              </button>
            </div>
          </div>
        </div>
      )}

      {asking && confirming && (
        <div className="modal-backdrop" onClick={() => setConfirming(false)}>
          <div
            className="modal"
            role="dialog"
            aria-modal="true"
            aria-label="Delete for good"
            onClick={(event) => event.stopPropagation()}
          >
            <h2 className="modal-title">Delete for good?</h2>
            <div className="modal-body">
              <p>
                {asking.name} ({bytes(asking.size)}) would be deleted. It does not go to the
                Trash and cannot be brought back.
              </p>
              <p style={{ color: 'var(--dim)', fontSize: 12.5 }}>
                Nothing is deleted here — this is the sample machine's inventory.
              </p>
            </div>
            <div className="modal-actions">
              <button className="button" onClick={() => setConfirming(false)} autoFocus>
                Cancel
              </button>
              <button
                className="button danger"
                onClick={() => {
                  setNotice(`On your own machine ${asking.name} would be deleted for good.`)
                  setConfirming(false)
                  setAsking(null)
                }}
              >
                Delete for good
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  )
}
