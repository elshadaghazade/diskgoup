/** Formatting helpers shared by the UI. */

const UNITS = ['B', 'KB', 'MB', 'GB', 'TB', 'PB'] as const

/** Render a byte count the way the CLI does (1024-based units). */
export function bytes(size: number, precision?: number): string {
  if (!Number.isFinite(size)) return '—'
  const negative = size < 0
  let value = Math.abs(size)
  if (value < 1024) return `${negative ? '-' : ''}${Math.round(value)} B`
  let unit = 0
  while (value >= 1024 && unit < UNITS.length - 1) {
    value /= 1024
    unit += 1
  }
  const digits = precision ?? (value >= 10 ? 0 : 1)
  return `${negative ? '-' : ''}${value.toFixed(digits)} ${UNITS[unit]}`
}

/** Render a fraction as a percentage. */
export function percent(part: number, whole: number, digits = 1): string {
  if (!whole) return '0.0%'
  return `${((part / whole) * 100).toFixed(digits)}%`
}

/** Render a count with thin separators. */
export function count(value: number): string {
  return value.toLocaleString()
}

/** Render a timestamp as a date. */
export function date(value: number): string {
  return new Date(value * 1000).toLocaleString()
}

/** A short date. */
export function shortDate(value: number): string {
  return new Date(value * 1000).toLocaleDateString()
}

/** Render a duration in seconds. */
export function duration(seconds: number): string {
  if (seconds < 1) return `${Math.round(seconds * 1000)}ms`
  if (seconds < 60) return `${seconds.toFixed(1)}s`
  const minutes = Math.floor(seconds / 60)
  const rest = Math.round(seconds % 60)
  if (minutes < 60) return `${minutes}m ${String(rest).padStart(2, '0')}s`
  const hours = Math.floor(minutes / 60)
  return `${hours}h ${String(minutes % 60).padStart(2, '0')}m`
}

/** The colour used for a file kind, matching the CLI's palette. */
export const KIND_COLORS: Record<string, string> = {
  game: '#e056a0',
  video: '#ef6461',
  audio: '#c678dd',
  image: '#56b6c2',
  archive: '#f5a623',
  document: '#4ab3c4',
  code: '#7f848e',
  cache: '#5ac18e',
  application: '#5b8dee',
  system: '#5c6370',
  other: '#8b93a7',
}

export function kindColor(kind: string): string {
  return KIND_COLORS[kind] ?? KIND_COLORS.other
}

/** Truncate a path for display, keeping the tail visible. */
export function shortenPath(path: string, max = 48): string {
  if (path.length <= max) return path
  return `…${path.slice(path.length - max + 1)}`
}

/**
 * The last segment of a path — the file or folder name.
 *
 * The path comes from the CLI, so it carries the separator of the platform
 * that produced it; both are handled here.
 */
export function baseName(path: string): string {
  const parts = path.split(/[/\\]/)
  return parts[parts.length - 1] || path
}

/**
 * Keep the last few segments of a path.
 *
 * The tail is what tells you where the scan is; the head is the volume you
 * already know about. Unlike a character cut, this keeps the depth of the
 * path readable.
 */
export function tailPath(path: string, segments = 2): string {
  const parts = path.split('/').filter(Boolean)
  if (parts.length <= segments) return path
  return `…/${parts.slice(-segments).join('/')}`
}
