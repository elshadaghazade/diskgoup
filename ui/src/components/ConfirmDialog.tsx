import { useEffect } from 'react'

type Props = {
  title: string
  body: string
  confirmLabel?: string
  /** The work is under way — the dialog says so and refuses a second click. */
  busy?: boolean
  busyLabel?: string
  onConfirm: () => void
  onCancel: () => void
}

/**
 * A modal that asks before something destructive happens.
 *
 * Cancel is focused on open, so a stray Enter cancels rather than confirms.
 */
export default function ConfirmDialog({
  title,
  body,
  confirmLabel = 'Delete',
  busy = false,
  busyLabel = 'Working…',
  onConfirm,
  onCancel,
}: Props) {
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape' && !busy) onCancel()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onCancel, busy])

  return (
    <div className="modal-backdrop" onClick={() => !busy && onCancel()}>
      <div
        className="modal"
        role="dialog"
        aria-modal="true"
        aria-label={title}
        onClick={(event) => event.stopPropagation()}
      >
        <h2 className="modal-title">{title}</h2>
        <p className="modal-body">{body}</p>
        {busy && (
          <p className="modal-busy" role="status">
            <span className="spinner" aria-hidden="true" />
            {busyLabel}
          </p>
        )}
        <div className="modal-actions">
          <button className="button" onClick={onCancel} autoFocus disabled={busy}>
            Cancel
          </button>
          <button className="button danger" onClick={onConfirm} disabled={busy}>
            {busy ? busyLabel : confirmLabel}
          </button>
        </div>
      </div>
    </div>
  )
}
