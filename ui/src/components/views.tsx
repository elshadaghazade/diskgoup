import { bytes } from '../lib/format'
import type { LayoutItem } from '../lib/types'

const CANVAS_W = 1200
const CANVAS_H = 800

type ViewProps = {
  items: LayoutItem[]
  onSelect?: (item: LayoutItem) => void
}

function polar(cx: number, cy: number, r: number, angle: number): [number, number] {
  return [cx + r * Math.cos(angle), cy + r * Math.sin(angle)]
}

/** Squarified treemap. */
export function TreemapView({ items, onSelect }: ViewProps) {
  return (
    <svg viewBox={`0 0 ${CANVAS_W} ${CANVAS_H}`} role="img" aria-label="Treemap">
      {items.map((item) => {
        const rect = item.rect
        if (!rect) return null
        const wide = rect.width > 70 && rect.height > 26
        return (
          <g
            key={item.path}
            className="tile"
            onClick={() => onSelect?.(item)}
          >
            <title>{`${item.name} — ${bytes(item.size)}`}</title>
            <rect
              x={rect.x}
              y={rect.y}
              width={Math.max(0, rect.width)}
              height={Math.max(0, rect.height)}
              fill={item.color}
              fillOpacity={0.85}
              stroke="#0d1117"
              strokeWidth={2}
            />
            {wide && (
              <>
                <text x={rect.x + 8} y={rect.y + 20} fill="#0d1117" fontSize={13} fontWeight={600}>
                  {truncate(item.name, Math.floor(rect.width / 8))}
                </text>
                {rect.height > 44 && (
                  <text x={rect.x + 8} y={rect.y + 38} fill="#0d1117" fontSize={11}>
                    {truncate(bytes(item.size), Math.floor(rect.width / 8))}
                  </text>
                )}
              </>
            )}
          </g>
        )
      })}
    </svg>
  )
}

/** Radial sunburst. */
export function SunburstView({ items, onSelect }: ViewProps) {
  const cx = CANVAS_W / 2
  const cy = CANVAS_H / 2
  const outer = Math.min(CANVAS_W, CANVAS_H) * 0.46
  const maxRadius = Math.max(1, ...items.map((item) => item.radius ?? 1))
  const ring = outer / maxRadius

  return (
    <svg viewBox={`0 0 ${CANVAS_W} ${CANVAS_H}`} role="img" aria-label="Sunburst">
      <circle cx={cx} cy={cy} r={ring * 0.55} fill="#161b22" stroke="#30363d" />
      {items.map((item) => {
        const radius = item.radius ?? 1
        const inner = ring * (radius - 1)
        const outerR = ring * radius
        const start = item.start_angle ?? 0
        const end = item.end_angle ?? 0
        if (end <= start) return null
        const path = arcPath(cx, cy, inner, outerR, start, end)
        if (!path) return null
        return (
          <path
            key={item.path}
            className="tile"
            d={path}
            fill={item.color}
            fillOpacity={0.88}
            stroke="#0d1117"
            strokeWidth={1.5}
            onClick={() => onSelect?.(item)}
          >
            <title>{`${item.name} — ${bytes(item.size)}`}</title>
          </path>
        )
      })}
    </svg>
  )
}

function arcPath(
  cx: number,
  cy: number,
  inner: number,
  outer: number,
  start: number,
  end: number,
): string | null {
  if (outer <= 0 || end <= start) return null
  const large = end - start > Math.PI ? 1 : 0
  const [x0, y0] = polar(cx, cy, outer, start)
  const [x1, y1] = polar(cx, cy, outer, end)
  if (inner <= 0) {
    return `M ${cx} ${cy} L ${x0} ${y0} A ${outer} ${outer} 0 ${large} 1 ${x1} ${y1} Z`
  }
  const [x2, y2] = polar(cx, cy, inner, end)
  const [x3, y3] = polar(cx, cy, inner, start)
  return (
    `M ${x0} ${y0} A ${outer} ${outer} 0 ${large} 1 ${x1} ${y1} ` +
    `L ${x2} ${y2} A ${inner} ${inner} 0 ${large} 0 ${x3} ${y3} Z`
  )
}

/** Flame graph (icicle). */
export function FlameView({ items, onSelect }: ViewProps) {
  const maxDepth = Math.max(0, ...items.map((item) => item.depth))
  const rowHeight = Math.min(34, Math.max(20, (CANVAS_H - 60) / (maxDepth + 1)))
  const total = Math.max(1, ...items.map((item) => item.radius ?? 0))
  const scale = (CANVAS_W - 32) / total

  return (
    <svg viewBox={`0 0 ${CANVAS_W} ${CANVAS_H}`} role="img" aria-label="Flame graph">
      {items.map((item) => {
        const width = (item.radius ?? 0) * scale
        if (width <= 0) return null
        const x = 16 + (item.x ?? 0) * scale
        const y = 40 + (item.depth ?? 0) * rowHeight
        return (
          <g key={item.path} className="tile" onClick={() => onSelect?.(item)}>
            <title>{`${item.name} — ${bytes(item.size)}`}</title>
            <rect
              x={x}
              y={y}
              width={width}
              height={rowHeight - 2}
              fill={item.color}
              fillOpacity={0.85}
              stroke="#0d1117"
            />
            {width > 60 && (
              <text x={x + 8} y={y + rowHeight - 12} fill="#0d1117" fontSize={11} fontWeight={600}>
                {truncate(item.name, Math.floor(width / 7))}
              </text>
            )}
          </g>
        )
      })}
    </svg>
  )
}

/** Bubble packing. */
export function BubblesView({ items, onSelect }: ViewProps) {
  return (
    <svg viewBox={`0 0 ${CANVAS_W} ${CANVAS_H}`} role="img" aria-label="Bubbles">
      {items.map((item) => {
        const radius = item.radius ?? 0
        if (radius <= 0) return null
        return (
          <g key={item.path} className="tile" onClick={() => onSelect?.(item)}>
            <title>{`${item.name} — ${bytes(item.size)}`}</title>
            <circle
              cx={item.x ?? 0}
              cy={item.y ?? 0}
              r={radius}
              fill={item.color}
              fillOpacity={0.72}
              stroke="#0d1117"
              strokeWidth={2}
            />
            {radius > 34 && (
              <text
                x={item.x ?? 0}
                y={item.y ?? 0}
                fill="#0d1117"
                fontSize={12}
                fontWeight={600}
                textAnchor="middle"
                dominantBaseline="middle"
              >
                {truncate(item.name, 16)}
              </text>
            )}
          </g>
        )
      })}
    </svg>
  )
}

/** Radial mind map. */
export function MindmapView({ items, onSelect }: ViewProps) {
  const byPath = new Map(items.map((item) => [item.path, item]))

  return (
    <svg viewBox={`0 0 ${CANVAS_W} ${CANVAS_H}`} role="img" aria-label="Mind map">
      {items.map((item) => {
        const parent = item.parent_path ? byPath.get(item.parent_path) : undefined
        if (!parent) return null
        return (
          <line
            key={`link-${item.path}`}
            x1={parent.x ?? 0}
            y1={parent.y ?? 0}
            x2={item.x ?? 0}
            y2={item.y ?? 0}
            stroke="#4b5563"
            strokeWidth={2}
          />
        )
      })}
      {items.map((item) => {
        const radius = item.radius ?? 8
        return (
          <g key={item.path} className="tile" onClick={() => onSelect?.(item)}>
            <title>{`${item.name} — ${bytes(item.size)}`}</title>
            <circle
              cx={item.x ?? 0}
              cy={item.y ?? 0}
              r={Math.min(radius, 26)}
              fill={item.color}
              fillOpacity={0.9}
              stroke="#0d1117"
              strokeWidth={2}
            />
            {radius > 20 && (
              <text
                x={item.x ?? 0}
                y={(item.y ?? 0) + radius + 16}
                fill="#8b949e"
                fontSize={11}
                textAnchor="middle"
              >
                {truncate(item.name, 20)}
              </text>
            )}
          </g>
        )
      })}
    </svg>
  )
}

function truncate(text: string, limit: number): string {
  if (limit <= 1 || text.length <= limit) return text
  return `${text.slice(0, Math.max(1, limit - 1))}…`
}
