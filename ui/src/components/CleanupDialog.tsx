import { useEffect, useState } from 'react'
import { api } from '../lib/api'
import { baseName, bytes, count } from '../lib/format'
import type { ScanRef, StagedItem } from '../lib/types'
import ConfirmDialog from './ConfirmDialog'

type Props = {
  scanRef: ScanRef
  onClose: () => void
  /** The paths that were removed, and whether they went for good. */
  onCommitted: (moved: string[], permanent: boolean) => void
}

/**
 * The review list.
 *
 * Nothing is removed until this dialog is confirmed: the staged items are
 * listed with their sizes, each one can be taken back, and the confirmation
 * re-validates every item before it is moved to the recycle bin.
 */
export default function CleanupDialog({ scanRef, onClose, onCommitted }: Props) {
  const [items, setItems] = useState<StagedItem[]>([])
  const [total, setTotal] = useState(0)
  const [issues, setIssues] = useState<string[]>([])
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [asking, setAsking] = useState(false)

  useEffect(() => {
    api
      .cleanupList(scanRef)
      .then((result) => {
        setItems(result.items)
        setTotal(result.total)
      })
      .catch((err: Error) => setError(err.message))
  }, [scanRef])

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  /** Take one item back off the list. */
  const remove = async (path: string) => {
    setBusy(true)
    setError('')
    try {
      await api.unstage(scanRef, [path])
      const result = await api.cleanupList(scanRef)
      setItems(result.items)
      setTotal(result.total)
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setBusy(false)
    }
  }

  /** Validate, then remove the list — to the trash, or for good. */
  const commit = async (permanent: boolean) => {
    setBusy(true)
    setError('')
    setIssues([])
    try {
      const validation = await api.cleanupValidate(scanRef)
      if (validation.issues.length > 0) {
        setIssues(validation.issues.map((issue) => `${issue.path}: ${issue.reason}`))
        return
      }
      const result = await api.cleanupCommit(scanRef, permanent)
      if (result.failed.length > 0) {
        // Something could not be removed. The review stays open and says
        // what happened — closing it here would take the message with it.
        setError(result.failed.map((item) => `${item.path}: ${item.reason}`).join(' '))
        const listed = await api.cleanupList(scanRef)
        setItems(listed.items)
        setTotal(listed.total)
        return
      }
      if (result.moved.length > 0) onCommitted(result.moved, permanent)
      else onClose()
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <>
      <div className="modal-backdrop" onClick={onClose}>
        <div
          className="modal"
          role="dialog"
          aria-modal="true"
          aria-label="Review cleanup"
          onClick={(event) => event.stopPropagation()}
        >
          <h2 className="modal-title">Review cleanup</h2>

          <div className="modal-body">
            <p>
              Only the items you approve are removed. Moving them to the trash keeps them
              recoverable — the space comes back when the trash is emptied.
            </p>

            {items.length === 0 ? (
              <div className="empty-state">
                <div>The review list is empty.</div>
              </div>
            ) : (
              <div className="cleanup-list">
                {items.map((item) => (
                  <div className="row" key={item.path}>
                    <span className="name" title={item.path}>
                      {baseName(item.path)}
                    </span>
                    <span className="size">{bytes(item.size)}</span>
                    <button
                      className="drop"
                      onClick={() => void remove(item.path)}
                      disabled={busy}
                      aria-label={`Take ${baseName(item.path)} off the list`}
                      title="Take off the list"
                    >
                      ×
                    </button>
                  </div>
                ))}
              </div>
            )}

            <div className="cleanup-total">
              Total: {bytes(total)} · {count(items.length)} items
            </div>

            {issues.length > 0 && (
              <div className="form-error">
                {issues.map((issue) => (
                  <div key={issue}>{issue}</div>
                ))}
              </div>
            )}
            {error && <div className="form-error">{error}</div>}
          </div>

          <div className="modal-actions">
            <button className="button" onClick={onClose} autoFocus>
              Cancel
            </button>
            <button
              className="button primary"
              onClick={() => void commit(false)}
              disabled={busy || items.length === 0}
              title="Move to the recycle bin — recoverable"
            >
              Move to Trash
            </button>
            <button
              className="button danger"
              onClick={() => setAsking(true)}
              disabled={busy || items.length === 0}
              title="Delete for good — nothing goes to the recycle bin"
            >
              Delete permanently
            </button>
          </div>
        </div>
      </div>

      {asking && (
        <ConfirmDialog
          title="Delete for good?"
          body={`${count(items.length)} item${items.length > 1 ? 's' : ''} (${bytes(total)}) will be deleted. They do not go to the recycle bin and cannot be brought back.`}
          confirmLabel="Delete for good"
          onConfirm={() => {
            setAsking(false)
            void commit(true)
          }}
          onCancel={() => setAsking(false)}
        />
      )}
    </>
  )
}
