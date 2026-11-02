import { GitHubMark } from '@/components/site/github-mark'
import { Button } from '@/components/ui/button'

const LINKS = [
  { href: '#explore', label: 'Explore' },
  { href: '#features', label: 'Features' },
  { href: '#cli', label: 'CLI' },
  { href: '#download', label: 'Download' },
]

export function Logo({ className = '' }: { className?: string }) {
  return (
    <span className={`flex items-center gap-2.5 ${className}`}>
      <span className="grid size-8 place-items-center rounded-lg bg-gradient-to-br from-accent to-accent-deep text-[13px] font-extrabold text-accent-ink">
        D
      </span>
      <span className="text-[15px] font-bold tracking-tight text-ink">DiskGOup</span>
    </span>
  )
}

export default function Header() {
  return (
    <header className="sticky top-0 z-50 border-b border-line/70 bg-canvas/80 backdrop-blur-xl">
      <div className="mx-auto flex h-16 max-w-6xl items-center gap-8 px-6">
        <a href="#top" aria-label="DiskGOup home">
          <Logo />
        </a>

        <nav className="hidden items-center gap-7 text-sm text-muted md:flex">
          {LINKS.map((link) => (
            <a key={link.href} href={link.href} className="transition-colors hover:text-ink">
              {link.label}
            </a>
          ))}
          <a
            href="https://diskgoup-docs.vercel.app/"
            className="transition-colors hover:text-ink"
            rel="noreferrer"
            target="_blank"
          >
            Docs
          </a>
        </nav>

        <div className="ml-auto flex items-center gap-3">
          <Button asChild variant="outline" size="sm">
            <a href="https://github.com/elshadaghazade/diskgoup" rel="noreferrer" target="_blank">
              <GitHubMark />
              <span className="hidden sm:inline">GitHub</span>
            </a>
          </Button>
          <Button asChild size="sm">
            <a href="#download">Download</a>
          </Button>
        </div>
      </div>
    </header>
  )
}
