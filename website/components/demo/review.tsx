'use client'

import { bytes, count } from './format'

export type ReviewItem = {
  name: string
  path: string
  size: number
}

type Props = {
  items: ReviewItem[]
  /** The heading of the review. */
  title?: string
  onClose: () => void
  onConfirm: () => void
}

/**
 * The review list.
 *
 * On your own machine this is where a staged cleanup waits for your approval
 * before anything is moved to the recycle bin. Here it shows what the real
 * app would put on that list — and touches nothing.
 */
export default function Review({ items, title = 'Review before anything is removed', onClose, onConfirm }: Props) {
  const total = items.reduce((sum, item) => sum + item.size, 0)

  return (
    <div className="modal-backdrop" role="dialog" aria-modal="true" aria-label="Review list">
      <div className="modal">
        <div className="modal-title">{title}</div>
        <div className="modal-body">
          <div className="cleanup-list">
            {items.map((item) => (
              <div className="row" key={item.path}>
                <span className="name">{item.name}</span>
                <span className="size">{bytes(item.size)}</span>
              </div>
            ))}
          </div>
          <div className="cleanup-total">
            {count(items.length)} item{items.length === 1 ? '' : 's'} · {bytes(total)}
          </div>
          <p style={{ color: 'var(--dim)', fontSize: 12.5, marginBottom: 0 }}>
            On your own machine this list is validated against the index and then moved to the
            recycle bin — never deleted outright. Here it is only a preview: nothing is read,
            nothing is written, and no file of yours is involved.
          </p>
        </div>
        <div className="modal-actions">
          <button className="button" onClick={onClose}>
            Close
          </button>
          <button className="button primary" onClick={onConfirm}>
            Confirm
          </button>
        </div>
      </div>
    </div>
  )
}
