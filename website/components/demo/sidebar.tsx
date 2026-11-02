'use client'

import { bytes, kindColor, percent, shortDate } from './format'
import type { KindTotal, ScanMeta, Volume } from './types'

type Props = {
  volumes: Volume[]
  scan: ScanMeta
  types: KindTotal[]
}

/** A donut showing how much of the volume is in use. */
function UsageRing({ used, total }: { used: number; total: number }) {
  const ratio = total ? Math.min(1, used / total) : 0
  const radius = 26
  const circumference = 2 * Math.PI * radius
  const dash = circumference * ratio

  return (
    <svg width="64" height="64" viewBox="0 0 64 64" role="img" aria-label="Disk usage">
      <circle cx="32" cy="32" r={radius} fill="none" stroke="#21262d" strokeWidth="7" />
      <circle
        cx="32"
        cy="32"
        r={radius}
        fill="none"
        stroke={ratio > 0.9 ? '#ef6461' : '#f5a623'}
        strokeWidth="7"
        strokeLinecap="round"
        strokeDasharray={`${dash} ${circumference}`}
        transform="rotate(-90 32 32)"
      />
      <text
        x="32"
        y="33"
        textAnchor="middle"
        dominantBaseline="middle"
        fill="#e6edf3"
        fontSize="12"
        fontWeight="700"
      >
        {(ratio * 100).toFixed(0)}%
      </text>
      <text x="32" y="44" textAnchor="middle" fill="#8b949e" fontSize="7">
        used
      </text>
    </svg>
  )
}

/**
 * The left panel: the volumes of the machine, the scans in the index and the
 * breakdown of what the open scan holds.
 */
export default function Sidebar({ volumes, scan, types }: Props) {
  const volume = volumes.find((item) => scan.root.startsWith(item.mountpoint))
  const used = volume ? volume.used : scan.total_size
  const total = volume ? volume.total : 0

  return (
    <aside className="sidebar">
      <div className="sidebar-section">
        <div className="sidebar-label">Disk storage</div>
        <div className="usage-ring">
          <UsageRing used={used} total={total} />
          <dl className="metrics">
            <div>
              <dt>Total</dt>
              <dd>{bytes(total)}</dd>
            </div>
            <div>
              <dt>Used</dt>
              <dd className="up">{bytes(used)}</dd>
            </div>
            <div>
              <dt>Free</dt>
              <dd className="down">{bytes(Math.max(0, total - used))}</dd>
            </div>
          </dl>
        </div>
      </div>

      <div className="sidebar-section">
        <div className="sidebar-label">Volumes</div>
        {volumes.map((item) => (
          <div
            key={item.mountpoint}
            className={`sidebar-item${scan.root.startsWith(item.mountpoint) ? ' active' : ''}`}
            style={{ cursor: 'default' }}
            title={item.mountpoint}
          >
            <span aria-hidden>⛁</span>
            <span>{item.label}</span>
            <span className="value">{percent(item.used, item.total, 0)}</span>
          </div>
        ))}
      </div>

      <div className="sidebar-section">
        <div className="sidebar-label">Scans</div>
        <div className="sidebar-item active">
          <button className="scan-open" title={`${scan.root} · ${bytes(scan.total_size)}`}>
            <span aria-hidden>◷</span>
            <span>{scan.root.split('/').pop() || scan.root}</span>
            <span className="value">{bytes(scan.total_size)}</span>
          </button>
        </div>
        <div className="sidebar-hint">
          Scanned {shortDate(scan.finished_at)} · every scan is kept in the index.
        </div>
      </div>

      {types.length > 0 && (
        <div className="sidebar-section">
          <div className="sidebar-label">File types</div>
          {types.map((item) => (
            <div key={item.kind} className="sidebar-item" style={{ cursor: 'default' }}>
              <span className="kind-dot" style={{ background: kindColor(item.kind) }} />
              <span>{item.kind}</span>
              <span className="value">{bytes(item.size)}</span>
            </div>
          ))}
        </div>
      )}
    </aside>
  )
}
