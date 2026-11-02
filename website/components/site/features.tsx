import {
  Boxes,
  Copy,
  FileSearch,
  HardDrive,
  Layers,
  ShieldCheck,
  Terminal,
} from 'lucide-react'
import { Card, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'

const FEATURES = [
  {
    icon: Layers,
    title: 'One scan, nine views',
    body: 'The folder browser, treemap, sunburst, flame graph, bubbles, mind map, top sizes and age map are all projections of the same result — the disk is walked once.',
  },
  {
    icon: Copy,
    title: 'Duplicates by content',
    body: 'Equal names are not proof. Every candidate is verified with SHA-256 and an exact byte comparison, and the extra copies are grouped for review.',
  },
  {
    icon: ShieldCheck,
    title: 'Nothing is deleted on the spot',
    body: 'A cleanup is staged, reviewed, validated and confirmed before anything moves — and then it goes to the recycle bin, not to oblivion.',
  },
  {
    icon: Terminal,
    title: 'Scriptable from the first call',
    body: 'Every command speaks JSON. Pipe a scan into jq, feed the index to your own scripts, and drive the desktop app from the same CLI.',
  },
  {
    icon: HardDrive,
    title: 'The same on three platforms',
    body: 'macOS, Windows and Linux get the same capabilities, the same commands and the same index format. The tool on your laptop is the tool on your desktop.',
  },
  {
    icon: Boxes,
    title: 'A permanent, reusable index',
    body: 'Scans are kept in a SQLite index. Open last week’s scan today — it is still there, and it is still accurate.',
  },
]

export default function Features() {
  return (
    <section id="features" className="border-t border-line/70 py-24">
      <div className="mx-auto max-w-6xl px-6">
        <div className="max-w-2xl">
          <p className="text-sm font-medium uppercase tracking-[0.18em] text-accent">What it does</p>
          <h2 className="mt-4 text-balance text-3xl font-bold tracking-tight text-ink sm:text-4xl">
            A free, open-source disk analyzer that does the whole job
          </h2>
          <p className="mt-4 text-base leading-relaxed text-muted">
            The commercial tools in this space do it well — but they are closed-source, each one
            targets a single platform, and every one of them is GUI-only. DiskGOup does the same job
            with the source open and a CLI at the centre.
          </p>
        </div>

        <div className="mt-14 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
          {FEATURES.map((feature) => (
            <Card key={feature.title} className="h-full">
              <CardHeader>
                <span className="mb-3 grid size-10 place-items-center rounded-xl border border-accent/25 bg-accent/10 text-accent">
                  <feature.icon className="size-5" />
                </span>
                <CardTitle>{feature.title}</CardTitle>
                <CardDescription>{feature.body}</CardDescription>
              </CardHeader>
            </Card>
          ))}
        </div>

        <div className="mt-6 flex items-center gap-3 rounded-2xl border border-line bg-surface/60 px-5 py-4 text-sm text-muted">
          <FileSearch className="size-4 shrink-0 text-accent" />
          <p>
            Advanced search, archive preview, application inventory, game library discovery, a live
            monitor, snapshots with a seven-day diff, and a weekly HTML report — all in the same
            window, all reading the same scan.
          </p>
        </div>
      </div>
    </section>
  )
}
