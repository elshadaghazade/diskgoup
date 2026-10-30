import { useEffect, useMemo, useState } from 'react'
import { api } from '../lib/api'
import { bytes, count, kindColor, percent } from '../lib/format'
import type {
  AgeBucket,
  LayoutItem,
  LayoutResponse,
  ScanMeta,
  ScanRef,
  SizeEntry,
} from '../lib/types'
import {
  BubblesView,
  FlameView,
  MindmapView,
  SunburstView,
  TreemapView,
} from './views'

type ViewId =
  | 'folders'
  | 'treemap'
  | 'sunburst'
  | 'flame'
  | 'bubbles'
  | 'mindmap'
  | 'sizes'
  | 'age'

const VIEWS: { id: ViewId; label: string }[] = [
  { id: 'folders', label: 'Folders' },
  { id: 'treemap', label: 'Treemap' },
  { id: 'sunburst', label: 'Sunburst' },
  { id: 'flame', label: 'Flame' },
  { id: 'bubbles', label: 'Bubbles' },
  { id: 'mindmap', label: 'Mind map' },
  { id: 'sizes', label: 'Top sizes' },
  { id: 'age', label: 'Age map' },
]

const SPATIAL: ViewId[] = ['treemap', 'sunburst', 'flame', 'bubbles', 'mindmap']

type Props = {
  scanRef: ScanRef | null
  scan: ScanMeta | null
  scans: ScanMeta[]
  filter: string
}

export default function ExploreTab({ scanRef, scan, scans, filter }: Props) {
  const [view, setView] = useState<ViewId>('folders')
  const [sizes, setSizes] = useState<SizeEntry[]>([])
  const [layout, setLayout] = useState<LayoutResponse | null>(null)
  const [buckets, setBuckets] = useState<AgeBucket[]>([])
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (!scanRef) return
    let cancelled = false

    if (view === 'sizes' || view === 'folders') {
      setLoading(true)
      api
        .sizes(scanRef, view === 'sizes' ? 60 : 40)
        .then((result) => {
          if (!cancelled) setSizes(result.entries)
        })
        .catch((err: Error) => !cancelled && setError(err.message))
        .finally(() => !cancelled && setLoading(false))
    }

    if (SPATIAL.includes(view)) {
      setLoading(true)
      api
        .layout(scanRef, view)
        .then((result) => {
          if (!cancelled) setLayout(result)
        })
        .catch((err: Error) => !cancelled && setError(err.message))
        .finally(() => !cancelled && setLoading(false))
    }

    if (view === 'age') {
      setLoading(true)
      api
        .age(scanRef)
        .then((result) => {
          if (!cancelled) setBuckets(result.buckets)
        })
        .catch((err: Error) => !cancelled && setError(err.message))
        .finally(() => !cancelled && setLoading(false))
    }

    return () => {
      cancelled = true
    }
  }, [scanRef, view])

  const folders = useMemo(
    () => sizes.filter((item) => item.is_dir).filter((item) => matches(item.name, filter)),
    [sizes, filter],
  )
  const largest = useMemo(
    () => sizes.filter((item) => !item.is_dir).filter((item) => matches(item.name, filter)),
    [sizes, filter],
  )

  if (!scanRef || !scan) {
    return (
      <div className="empty-state">
        <div>Nothing scanned yet.</div>
        <div className="hint">
          {scans.length > 0
            ? 'Open one of the scans in the index, on the left.'
            : 'Pick a volume on the left to scan it.'}
        </div>
      </div>
    )
  }

  return (
    <>
      <div className="workspace-heading">
        <h1>{scan.root.split('/').pop() || scan.root}</h1>
        <span className="summary">
          {bytes(scan.total_size)} · {count(scan.files)} files · {count(scan.folders)} folders
        </span>
      </div>

      <div className="view-toolbar">
        <div className="view-switcher" role="group" aria-label="View">
          {VIEWS.map((item) => (
            <button
              key={item.id}
              aria-pressed={view === item.id}
              onClick={() => setView(item.id)}
            >
              {item.label}
            </button>
          ))}
        </div>
        {loading && <span style={{ color: 'var(--dim)', fontSize: 12 }}>Loading…</span>}
      </div>

      <div className="workspace-content">
        {error && <div className="form-error">{error}</div>}

        {view === 'folders' && (
          <>
            <div className="folder-grid">
              {folders.map((item) => (
                <button
                  key={item.path}
                  className="folder-card"
                  onClick={() => void api.openPath(item.path)}
                  title={item.path}
                >
                  <span
                    className="glyph"
                    style={{ color: kindColor(item.kind) }}
                    aria-hidden
                  >
                    ▤
                  </span>
                  <span className="name">{item.name}</span>
                  <span className="meta">
                    <span className="size">{bytes(item.size)}</span>
                    <span>{percent(item.size, scan.total_size, 0)}</span>
                  </span>
                </button>
              ))}
              {folders.length === 0 && !loading && (
                <div className="empty-state">
                  <div>No folders match this filter.</div>
                </div>
              )}
            </div>

            {largest.length > 0 && (
              <div className="panel" style={{ marginTop: 16 }}>
                <h3>Largest files</h3>
                <table className="data">
                  <thead>
                    <tr>
                      <th>Name</th>
                      <th className="num">Size</th>
                      <th className="num">Share</th>
                    </tr>
                  </thead>
                  <tbody>
                    {largest.slice(0, 20).map((item) => (
                      <tr key={item.path}>
                        <td>
                          <span
                            className="kind-dot"
                            style={{ background: kindColor(item.kind) }}
                          />
                          {item.name}
                          {item.protected && (
                            <span className="badge protected" style={{ marginLeft: 8 }}>
                              protected
                            </span>
                          )}
                        </td>
                        <td className="num">{bytes(item.size)}</td>
                        <td className="num">{percent(item.size, scan.total_size)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </>
        )}

        {view === 'sizes' && (
          <table className="data">
            <thead>
              <tr>
                <th>#</th>
                <th>Name</th>
                <th>Type</th>
                <th className="num">Size</th>
                <th className="num">Share</th>
              </tr>
            </thead>
            <tbody>
              {sizes.map((item, index) => (
                <tr key={item.path}>
                  <td style={{ color: 'var(--dimmer)' }}>{index + 1}</td>
                  <td title={item.path}>
                    <span className="kind-dot" style={{ background: kindColor(item.kind) }} />
                    {item.name}
                  </td>
                  <td style={{ color: 'var(--dim)' }}>{item.is_dir ? 'folder' : item.kind}</td>
                  <td className="num">{bytes(item.size)}</td>
                  <td className="num">{percent(item.size, scan.total_size)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}

        {view === 'age' && (
          <div className="bar-list">
            {buckets.map((bucket) => (
              <div className="row" key={bucket.label}>
                <span>{bucket.label}</span>
                <span className="track">
                  <span
                    className="fill"
                    style={{
                      width: `${Math.max(0, bucket.share * 100)}%`,
                      background: '#f5a623',
                    }}
                  />
                </span>
                <span className="amount">
                  {bytes(bucket.size)} · {count(bucket.files)}
                </span>
              </div>
            ))}
          </div>
        )}

        {SPATIAL.includes(view) && layout && (
          <div className="canvas">
            {view === 'treemap' && <TreemapView items={layout.items} />}
            {view === 'sunburst' && <SunburstView items={layout.items} />}
            {view === 'flame' && <FlameView items={layout.items} />}
            {view === 'bubbles' && <BubblesView items={layout.items} />}
            {view === 'mindmap' && <MindmapView items={layout.items} />}
          </div>
        )}
      </div>
    </>
  )
}

function matches(name: string, filter: string): boolean {
  if (!filter) return true
  return name.toLowerCase().includes(filter.toLowerCase())
}

export type { LayoutItem }
