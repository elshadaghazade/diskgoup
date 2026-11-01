import { useEffect, useMemo, useState } from 'react'
import { api } from '../lib/api'
import { bytes, count } from '../lib/format'
import type { DuplicateGroup, DuplicateResponse, ScanMeta, ScanRef } from '../lib/types'
import CleanupDialog from './CleanupDialog'

type Props = { scanRef: ScanRef | null; scan: ScanMeta | null }

/** How many groups are drawn at once. */
const PAGE = 25

/**
 * Duplicate groups — content verified with SHA-256 and an exact byte compare.
 *
 * Every group can be cleaned: the copy the user keeps is marked, the rest
 * are the extra copies, and removing them goes through the same review list
 * as any other cleanup — so the protected paths are still refused and
 * nothing is removed before it is approved.
 */
export default function DuplicatesTab({ scanRef, scan }: Props) {
  const [result, setResult] = useState<DuplicateResponse | null>(null)
  const [error, setError] = useState('')
  const [note, setNote] = useState('')
  const [busy, setBusy] = useState(false)
  const [stage, setStage] = useState('')
  const [shown, setShown] = useState(PAGE)
  /** The copy the user keeps for each group — the oldest one by default. */
  const [keepers, setKeepers] = useState<Record<string, string>>({})
  const [reviewing, setReviewing] = useState(false)

  // The search runs on the CLI's worker thread, so the app keeps working
  // while it reads the disk. The stage it reached is reported as it goes.
  useEffect(
    () =>
      api.onNotification((notification) => {
        if (notification.method === 'duplicates.progress') {
          setStage((notification.params as { stage?: string }).stage ?? '')
        }
      }),
    [],
  )

  async function run() {
    if (!scanRef) return
    setBusy(true)
    setError('')
    setNote('')
    setStage('Starting…')
    try {
      const found = await api.duplicates(scanRef)
      setResult(found)
      setKeepers({})
      setShown(PAGE)
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setBusy(false)
      setStage('')
    }
  }

  const groups = result?.groups ?? []

  /** The copy that is kept for a group. */
  const keeperOf = (group: DuplicateGroup) => keepers[group.sha256] ?? group.keep ?? group.paths[0]

  /** The copies that are not kept — the space they hold. */
  const extrasOf = (group: DuplicateGroup) => group.paths.filter((path) => path !== keeperOf(group))

  const totalExtras = useMemo(
    () => groups.reduce((sum, group) => sum + extrasOf(group).length, 0),
    [groups, keepers],
  )

  /**
   * Put the extra copies on the review list.
   *
   * The CLI refuses the paths it must not touch — protected folders, game
   * data, the containers the system needs — and says why, so the user sees
   * what was left out.
   */
  async function removeExtras(paths: string[]) {
    if (!scanRef || paths.length === 0) return
    setBusy(true)
    setError('')
    setNote('')
    try {
      const staged = await api.stageCleanup(scanRef, paths)
      const refused = staged.refused.length
      const added = staged.staged.length
      setNote(
        `${count(added)} cop${added === 1 ? 'y' : 'ies'} on the review list` +
          (refused > 0 ? ` · ${count(refused)} refused (protected)` : ''),
      )
      if (added > 0) setReviewing(true)
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setBusy(false)
    }
  }

  /** The copies that were removed are no longer duplicates. */
  function onCommitted(moved: string[], permanent: boolean, freed: number) {
    setReviewing(false)
    const gone = new Set(moved)
    setResult((current) => {
      if (!current) return current
      const left = current.groups
        .map((group) => {
          const paths = group.paths.filter((path) => !gone.has(path))
          if (paths.length < 2) return null
          return {
            ...group,
            paths,
            copies: paths.length,
            reclaimable: group.size * (paths.length - 1),
          }
        })
        .filter((group): group is DuplicateGroup => group !== null)
      return {
        ...current,
        groups: left,
        group_count: left.length,
        total_reclaimable: left.reduce((sum, group) => sum + group.reclaimable, 0),
      }
    })
    setNote(
      permanent
        ? `${count(moved.length)} cop${moved.length === 1 ? 'y' : 'ies'} deleted for good — ${bytes(freed)} freed.`
        : `${count(moved.length)} cop${moved.length === 1 ? 'y' : 'ies'} moved to the recycle bin — the space comes back when the Trash is emptied.`,
    )
  }

  if (!scanRef || !scan) {
    return (
      <div className="empty-state">
        <div>Nothing scanned yet.</div>
        <div className="hint">Scan a volume before looking for duplicates.</div>
      </div>
    )
  }

  return (
    <>
      <div className="workspace-heading">
        <h1>Duplicates</h1>
        <span className="summary">Same content. Extra space.</span>
      </div>

      <div className="workspace-content">
        {error && <div className="form-error">{error}</div>}
        {note && <div className="browser-note">{note}</div>}

        <div className="panel">
          <h3>Find duplicates</h3>
          <p style={{ color: 'var(--dim)', fontSize: 12.5, marginTop: 0 }}>
            Content is verified with SHA-256 and an exact byte comparison. Equal names or
            sizes alone are never treated as proof. Zero-byte files and hard links to the
            same file are excluded.
          </p>
          <button className="button primary" onClick={() => void run()} disabled={busy}>
            {busy ? 'Scanning…' : 'Find duplicates'}
          </button>
          {busy && stage && (
            <div className="browser-note" style={{ marginTop: 10 }}>
              {stage}
            </div>
          )}
        </div>

        {result && (
          <>
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
                  <button
                    className="button small"
                    onClick={() =>
                      void removeExtras(groups.flatMap((group) => extrasOf(group)))
                    }
                    disabled={busy}
                    title="Put every extra copy on the review list"
                  >
                    Remove all extras
                  </button>
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
                  {groups.slice(0, shown).map((group) => {
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
                                    setKeepers((current) => ({
                                      ...current,
                                      [group.sha256]: path,
                                    }))
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
                              onClick={() => void removeExtras(extras)}
                              disabled={busy}
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

              {groups.length > shown && (
                <div className="browser-note">
                  Showing the first {count(shown)} of {count(groups.length)} groups.{' '}
                  <button className="button small" onClick={() => setShown(shown + PAGE)}>
                    Show more
                  </button>
                </div>
              )}

              {groups.length === 0 && (
                <div style={{ color: 'var(--dim)', fontSize: 13 }}>
                  No duplicates found in this scan.
                </div>
              )}
            </div>
          </>
        )}
      </div>

      {reviewing && (
        <CleanupDialog
          scanRef={scanRef}
          onClose={() => setReviewing(false)}
          onCommitted={onCommitted}
        />
      )}
    </>
  )
}
