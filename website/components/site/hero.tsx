import { ArrowRight, MonitorSmartphone, Terminal } from 'lucide-react'
import { GitHubMark } from '@/components/site/github-mark'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'

const FACTS = [
  { value: 'macOS · Windows · Linux', label: 'one binary, one index' },
  { value: '9 views', label: 'from a single scan' },
  { value: 'SHA-256', label: 'duplicates by content' },
  { value: 'MIT', label: 'free, forever' },
]

export default function Hero() {
  return (
    <section id="top" className="relative overflow-hidden">
      <div className="hero-grid pointer-events-none absolute inset-0 -z-10" />
      <div className="pointer-events-none absolute left-1/2 top-[-18rem] -z-10 h-[38rem] w-[68rem] -translate-x-1/2 rounded-full bg-accent/10 blur-[140px]" />

      <div className="mx-auto max-w-6xl px-6 pb-20 pt-24 text-center sm:pt-32">
        <Badge variant="accent" className="mb-7">
          <span className="size-1.5 animate-pulse-soft rounded-full bg-accent" />
          Open source · macOS, Windows and Linux
        </Badge>

        <h1 className="mx-auto max-w-4xl text-balance text-5xl font-bold leading-[1.05] tracking-tight text-ink sm:text-6xl lg:text-7xl">
          Take Control of Your
          <br className="hidden sm:block" /> Disk Space. <span className="text-gradient">For Free.</span>
        </h1>

        <p className="mx-auto mt-7 max-w-2xl text-pretty text-lg leading-relaxed text-muted">
          DiskGOup is an open-source disk space analyzer and duplicate finder with a desktop GUI
          and a scriptable CLI. It shows you exactly where your space went — by folder, by file
          type, by age and by content — and cleans up only what you approve.
        </p>

        <div className="mt-10 flex flex-col items-center justify-center gap-3 sm:flex-row">
          <Button asChild size="lg">
            <a href="#download">
              Download DiskGOup
              <ArrowRight />
            </a>
          </Button>
          <Button asChild variant="outline" size="lg">
            <a href="#explore">Try it in your browser</a>
          </Button>
        </div>

        <div className="mt-9 flex flex-wrap items-center justify-center gap-x-6 gap-y-3 text-sm text-faint">
          <span className="inline-flex items-center gap-2">
            <Terminal className="size-4" /> Every command takes --json
          </span>
          <span className="inline-flex items-center gap-2">
            <MonitorSmartphone className="size-4" /> Desktop app for all three platforms
          </span>
          <span className="inline-flex items-center gap-2">
            <GitHubMark /> MIT licensed
          </span>
        </div>

        <dl className="mx-auto mt-16 grid max-w-4xl grid-cols-2 gap-px overflow-hidden rounded-2xl border border-line bg-line lg:grid-cols-4">
          {FACTS.map((fact) => (
            <div key={fact.label} className="bg-surface/80 px-5 py-6 text-left">
              <dt className="text-sm font-semibold text-ink">{fact.value}</dt>
              <dd className="mt-1 text-xs text-faint">{fact.label}</dd>
            </div>
          ))}
        </dl>
      </div>
    </section>
  )
}
