import { useEffect, useState } from 'react'
import { api } from '../lib/api'
import { bytes, kindColor, percent, shortDate } from '../lib/format'
import type { KindTotal, ScanMeta, Volume } from '../lib/types'

type Props = {
  volumes: Volume[]
  scans: ScanMeta[]
  scan: ScanMeta | null
  busy: boolean
  onSelectRoot: (path: string) => void
  onOpenScan: (meta: ScanMeta) => void
  onRemoveScan: (meta: ScanMeta) => void
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

export default function Sidebar({
  volumes,
  scans,
  scan,
  busy,
  onSelectRoot,
  onOpenScan,
  onRemoveScan,
}: Props) {
  const [types, setTypes] = useState<KindTotal[]>([])

  useEffect(() => {
    if (!scan) {
      setTypes([])
      return
    }
    let cancelled = false
    api
      .types({ path: scan.root, scanId: scan.scan_id })
      .then((result) => {
        if (!cancelled) setTypes(result.types)
      })
      .catch(() => {
        if (!cancelled) setTypes([])
      })
    return () => {
      cancelled = true
    }
  }, [scan])

  const root = scan?.root ?? ''
  const volume = volumes.find((item) => root.startsWith(item.mountpoint))
  const used = volume ? volume.used : scan?.total_size ?? 0
  const total = volume ? volume.total : 0

  return (
    <aside className="sidebar">
      <button
        className="button primary"
        onClick={() => onSelectRoot(root || volumes[0]?.mountpoint || '')}
        disabled={busy || !volumes.length}
        style={{ width: '100%' }}
        title={root ? `Scan ${root} again` : 'Scan the first volume'}
      >
        {root ? '↻ Rescan' : '⛁ Scan drive'}
      </button>

      {volume && (
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
      )}

      {volumes.length > 0 && (
        <div className="sidebar-section">
          <div className="sidebar-label">Volumes</div>
          {volumes.map((item) => (
            <button
              key={item.mountpoint}
              className={`sidebar-item ${root.startsWith(item.mountpoint) ? 'active' : ''}`}
              onClick={() => onSelectRoot(item.mountpoint)}
              title={item.mountpoint}
            >
              <span aria-hidden>⛁</span>
              <span>{item.label}</span>
              <span className="value">{percent(item.used, item.total, 0)}</span>
            </button>
          ))}
        </div>
      )}

      {scans.length > 0 && (
        <div className="sidebar-section">
          <div className="sidebar-label">Scans</div>
          {scans.map((item) => (
            <div
              key={item.scan_id}
              className={`sidebar-item ${item.scan_id === scan?.scan_id ? 'active' : ''}`}
            >
              <button
                className="scan-open"
                onClick={() => onOpenScan(item)}
                title={`${item.root} · ${bytes(item.total_size)} · ${shortDate(item.finished_at)}`}
              >
                <span aria-hidden>{item.complete ? '◷' : '◌'}</span>
                <span>{item.root.split('/').pop() || item.root}</span>
                <span className="value">{bytes(item.total_size)}</span>
              </button>
              <button
                className="scan-remove"
                onClick={() => onRemoveScan(item)}
                title="Remove this scan from the index"
                aria-label={`Remove the scan of ${item.root}`}
              >
                ×
              </button>
            </div>
          ))}
        </div>
      )}

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
