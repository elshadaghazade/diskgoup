'use client'

import { useEffect, useState } from 'react'
import type {
  AgeBucket,
  BrowserFolder,
  DuplicateResponse,
  KindTotal,
  LayoutItem,
  ScanMeta,
  SizeEntry,
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
