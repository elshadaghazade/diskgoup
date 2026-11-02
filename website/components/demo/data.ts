'use client'

import { useEffect, useState } from 'react'
import type {
  AgeBucket,
  Application,
  BrowserFolder,
  Comparison,
  DemoArchive,
  DuplicateResponse,
  GameLibrary,
  KindTotal,
  LayoutItem,
  MonitorSample,
  ScanMeta,
  SizeEntry,
  Snapshot,
  Volume,
} from './types'

/**
 * The sample disk the demo runs on.
 *
 * Every field was produced by the real CLI over a synthetic disk, so the
 * numbers, the colours and the layouts are the ones the desktop app shows.
 */
export type DemoData = {
  scan: ScanMeta
  volumes: Volume[]
  root: string
  folders: Record<string, BrowserFolder>
  sizes: SizeEntry[]
  types: KindTotal[]
  age: AgeBucket[]
  reclaimable: BrowserFolder
  layouts: Record<string, LayoutItem[]>
  duplicates: DuplicateResponse
  /** The ZIP archives of the sample disk, with their listings. */
  archives: DemoArchive[]
  /** The applications of the sample machine. */
  applications: { applications: Application[]; total_size: number }
  /** The game libraries of the sample machine. */
  games: { libraries: GameLibrary[]; total_size: number }
  /** A monitor sample of the sample machine. */
  monitor: MonitorSample
  /** The snapshots taken of the sample disk. */
  snapshots: Snapshot[]
  /** The current sizes measured against the oldest snapshot. */
  comparison: Comparison
  /** The weekly report and the file-type report of the sample disk. */
  reports: { weekly: string; csv: string }
}

/** Load the sample disk once, when the demo first appears. */
export function useDemoData() {
  const [data, setData] = useState<DemoData | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    let cancelled = false
    fetch('/demo.json')
      .then((response) => {
        if (!response.ok) throw new Error(`the sample disk could not be loaded (${response.status})`)
        return response.json()
      })
      .then((json: DemoData) => {
        if (!cancelled) setData(json)
      })
      .catch((err: Error) => {
        if (!cancelled) setError(err.message)
      })
    return () => {
      cancelled = true
    }
  }, [])

  return { data, error }
}
