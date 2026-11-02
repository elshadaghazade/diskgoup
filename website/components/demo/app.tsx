'use client'

import { useMemo, useState } from 'react'
import Browser from './browser'
import Duplicates from './duplicates'
import Inspector from './inspector'
import Sidebar from './sidebar'
import { BubblesView, FlameView, MindmapView, SunburstView, TreemapView } from './views'
import { bytes, count, kindColor, percent } from './format'
import type { DemoData } from './data'
import type { BrowserEntry } from './types'

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

/** Arrows pointing outward — the side panels hide, the workspace widens. */
function ExpandIcon() {
  return (
    <svg width="15" height="15" viewBox="0 0 14 14" aria-hidden="true">
      <path
        d="M4.5 2 1.5 5l3 3M9.5 2l3 3-3 3"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.4"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  )
}

/** Arrows pointing inward — the side panels come back. */
function CollapseIcon() {
  return (
    <svg width="15" height="15" viewBox="0 0 14 14" aria-hidden="true">
      <path
        d="M1.5 2l3 3-3 3M12.5 2l-3 3 3 3"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.4"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  )
}

/**
 * The desktop app, running in the browser on a sample disk.
 *
 * The components are the ones the Electron app renders — the same folder
 * browser, the same eight views, the same inspector — with the CLI replaced
 * by the payloads the CLI produced for the sample disk.
 */
export default function DemoApp({ data }: { data: DemoData }) {
  const [view, setView] = useState<ViewId>('folders')
  const [tab, setTab] = useState<'explore' | 'duplicates'>('explore')
  const [selected, setSelected] = useState<BrowserEntry | null>(null)
  const [filter, setFilter] = useState('')
  const [focus, setFocus] = useState(false)

  const scan = data.scan
  const layout = data.layouts[view]

  const workspace = useMemo(() => {
    if (tab === 'duplicates') return <Duplicates result={data.duplicates} />

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
        </div>

        {view === 'folders' ? (
          <Browser
            scan={scan}
            folders={data.folders}
            reclaimable={data.reclaimable}
            filter={filter}
            onSelect={setSelected}
          />
        ) : (
          <div className="workspace-content">
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
                  {data.sizes.map((item, index) => (
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
                {data.age.map((bucket) => (
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
                {view === 'treemap' && <TreemapView items={layout} />}
                {view === 'sunburst' && <SunburstView items={layout} />}
                {view === 'flame' && <FlameView items={layout} />}
                {view === 'bubbles' && <BubblesView items={layout} />}
                {view === 'mindmap' && <MindmapView items={layout} />}
              </div>
            )}
          </div>
        )}
      </>
    )
  }, [tab, view, data, scan, filter])

  return (
    <div className="dg-app h-full">
      <div className="app">
        <header className="app-topbar">
          <div className="brand">
            <span className="brand-mark">D</span>
            DiskGOup
          </div>

          <nav className="tabs" role="tablist" aria-label="Sections">
            <button
              role="tab"
              aria-selected={tab === 'explore'}
              className="tab"
              onClick={() => {
                setTab('explore')
                setSelected(null)
              }}
            >
              Explore
            </button>
            <button
              role="tab"
              aria-selected={tab === 'duplicates'}
              className="tab"
              onClick={() => {
                setTab('duplicates')
                setSelected(null)
              }}
            >
              Duplicates
            </button>
          </nav>

          <div className="topbar-spacer" />

          {tab !== 'duplicates' && (
            <label className="search-field">
              <span aria-hidden>⌕</span>
              <input
                value={filter}
                onChange={(event) => setFilter(event.target.value)}
                placeholder="Filter by name…"
                aria-label="Filter by name"
              />
            </label>
          )}

          <button
            className="icon-button"
            onClick={() => setFocus((value) => !value)}
            title={focus ? 'Show the side panels (Esc)' : 'Hide the side panels'}
            aria-label={focus ? 'Show the side panels' : 'Hide the side panels'}
            aria-pressed={focus}
          >
            {focus ? <CollapseIcon /> : <ExpandIcon />}
          </button>
        </header>

        <div className={`app-body${focus ? ' focus' : ''}`}>
          <Sidebar volumes={data.volumes} scan={scan} types={data.types} />

          <main className="workspace">{workspace}</main>

          <Inspector scan={scan} selected={selected} />
        </div>

        <footer className="status-bar">
          <span className="indicator">
            <span className="led" />
            Sample disk
          </span>
          <span className="spacer" />
          <span>Nothing here reads or changes your files</span>
        </footer>
      </div>
    </div>
  )
}
