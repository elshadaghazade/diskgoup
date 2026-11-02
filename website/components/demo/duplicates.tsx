'use client'

import { useMemo, useState } from 'react'
import { bytes, count } from './format'
import Review from './review'
import type { DuplicateGroup, DuplicateResponse } from './types'

type Props = {
  result: DuplicateResponse
}

/**
 * Duplicate groups — content verified with SHA-256 and an exact byte compare.
 *
 * The copy that is kept is marked, the rest are the extra copies, and
 * removing them goes through the same review list as any other cleanup.
 */
export default function Duplicates({ result }: Props) {
  const [keepers, setKeepers] = useState<Record<string, string>>({})
  const [review, setReview] = useState<DuplicateGroup[] | null>(null)

  const groups = result.groups

  /** The copy that is kept for a group. */
  const keeperOf = (group: DuplicateGroup) =>
    keepers[group.sha256] ?? group.keep ?? group.paths[0]

  /** The copies that are not kept — the space they hold. */
  const extrasOf = (group: DuplicateGroup) =>
    group.paths.filter((path) => path !== keeperOf(group))

  const totalExtras = useMemo(
    () => groups.reduce((sum, group) => sum + extrasOf(group).length, 0),
    [groups, keepers],
  )

  return (
    <>
      <div className="workspace-heading">
        <h1>Duplicates</h1>
        <span className="summary">Same content. Extra space.</span>
      </div>

      <div className="workspace-content">
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
          {totalExtras > 0 && (
            <div className="stat">
              <div className="label">Extra copies</div>
              <div className="value">{count(totalExtras)}</div>
            </div>
          )}
        </div>

        <div className="panel">
          <table className="data">
            <thead>
              <tr>
                <th className="num">Copies</th>
                <th className="num">Size</th>
                <th className="num">Reclaimable</th>
                <th>Paths</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {groups.map((group) => {
                const keeper = keeperOf(group)
                const extras = extrasOf(group)
                return (
                  <tr key={group.sha256}>
                    <td className="num">{group.copies}</td>
                    <td className="num">{bytes(group.size)}</td>
                    <td className="num">{bytes(group.reclaimable)}</td>
                    <td className="path">
                      {group.paths.map((path) => (
                        <div key={path}>
                          <label className="dup-keep">
                            <input
                              type="radio"
                              name={`keep-${group.sha256}`}
                              checked={path === keeper}
                              onChange={() =>
                                setKeepers((current) => ({ ...current, [group.sha256]: path }))
                              }
                            />
                            <span className="name">{path}</span>
                          </label>
                        </div>
                      ))}
                    </td>
                    <td>
                      {extras.length > 0 && (
                        <button
                          className="button small"
                          onClick={() => setReview([group])}
                          title={`Remove the ${extras.length} cop${extras.length === 1 ? 'y' : 'ies'} that are not kept`}
                        >
                          Remove {count(extras.length)}
                        </button>
                      )}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>

          {groups.length === 0 && (
            <div style={{ color: 'var(--dim)', fontSize: 13 }}>No duplicates found in this scan.</div>
          )}
        </div>
      </div>

      {review && (
        <Review
          title="Remove the extra copies?"
          items={review.flatMap((group) =>
            extrasOf(group).map((path) => ({
              name: path.split('/').pop() ?? path,
              path,
              size: group.size,
            })),
          )}
          onClose={() => setReview(null)}
          onConfirm={() => {
            setReview(null)
          }}
        />
      )}
    </>
  )
}
