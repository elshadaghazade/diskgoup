'use client'

import { Info } from 'lucide-react'
import DemoApp from '@/components/demo/app'
import { useDemoData } from '@/components/demo/data'

export default function DemoSection() {
  const { data, error } = useDemoData()

  return (
    <section id="explore" className="border-t border-line/70 py-24">
      <div className="mx-auto max-w-6xl px-6">
        <div className="max-w-2xl">
          <p className="text-sm font-medium uppercase tracking-[0.18em] text-accent">Live demo</p>
          <h2 className="mt-4 text-balance text-3xl font-bold tracking-tight text-ink sm:text-4xl">
            Explore DiskGOup, right here.
          </h2>
          <p className="mt-4 text-base leading-relaxed text-muted">
            This is the real desktop app, running in your browser. Click into a folder, switch
            between the eight views, open the duplicates and put something on the review list — the
            whole window works.
          </p>
        </div>

        <div className="mt-12 overflow-hidden rounded-2xl border border-edge bg-surface shadow-[0_40px_120px_-40px_rgba(0,0,0,0.9)]">
          <div className="flex items-center gap-3 border-b border-line bg-elevated px-4 py-3">
            <span className="flex gap-2">
              <span className="size-3 rounded-full bg-[#ff5f57]" />
              <span className="size-3 rounded-full bg-[#febc2e]" />
              <span className="size-3 rounded-full bg-[#28c840]" />
            </span>
            <span className="ml-2 truncate text-xs text-faint">
              DiskGOup — sample disk · /Users/demo
            </span>
            <span className="ml-auto hidden text-[11px] text-faint sm:block">
              interactive — click anything
            </span>
          </div>

          <div className="h-[620px] w-full">
            {data ? (
              <DemoApp data={data} />
            ) : error ? (
              <div className="grid h-full place-items-center px-6 text-center text-sm text-muted">
                {error}
              </div>
            ) : (
              <div className="grid h-full place-items-center gap-3 text-sm text-faint">
                <span className="size-5 animate-spin rounded-full border-2 border-edge border-t-accent" />
                Loading the sample disk…
              </div>
            )}
          </div>
        </div>

        <p className="mt-5 flex items-start gap-2.5 text-sm text-faint">
          <Info className="mt-0.5 size-4 shrink-0 text-accent" />
          <span>
            The demo runs on a <strong className="text-muted">synthetic sample disk</strong> — a
            made-up folder tree, a made-up inventory of applications and a made-up game library.
            Every number you see was produced by the real DiskGOup CLI scanning it. Nothing here
            reads, writes or deletes anything on your machine.
          </span>
        </p>
      </div>
    </section>
  )
}
