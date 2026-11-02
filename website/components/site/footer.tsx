import { GitHubMark } from '@/components/site/github-mark'
import { Logo } from './header'

const COLUMNS = [
  {
    title: 'Product',
    links: [
      { label: 'Download', href: '#download' },
      { label: 'Explore the demo', href: '#explore' },
      { label: 'Features', href: '#features' },
      { label: 'CLI reference', href: 'https://diskgoup.vercel.app/reference/cli/' },
    ],
  },
  {
    title: 'Documentation',
    links: [
      { label: 'Quick start', href: 'https://diskgoup.vercel.app/getting-started/quick-start/' },
      { label: 'Desktop app', href: 'https://diskgoup.vercel.app/desktop/overview/' },
      { label: 'Cleanup guide', href: 'https://diskgoup.vercel.app/guide/cleanup/' },
      { label: 'Building and releasing', href: 'https://diskgoup.vercel.app/development/building/' },
    ],
  },
  {
    title: 'Project',
    links: [
      { label: 'GitHub', href: 'https://github.com/elshadaghazade/diskgoup' },
      { label: 'Releases', href: 'https://github.com/elshadaghazade/diskgoup/releases' },
      { label: 'Issues', href: 'https://github.com/elshadaghazade/diskgoup/issues' },
      { label: 'Contributing', href: 'https://diskgoup.vercel.app/development/contributing/' },
    ],
  },
]

export default function Footer() {
  return (
    <footer className="border-t border-line/70 bg-surface/40">
      <div className="mx-auto max-w-6xl px-6 py-16">
        <div className="grid gap-10 md:grid-cols-[minmax(0,1.4fr)_repeat(3,minmax(0,1fr))]">
          <div>
            <Logo />
            <p className="mt-4 max-w-xs text-sm leading-relaxed text-muted">
              Take control of your disk space. Free, open-source and cross-platform — a desktop GUI
              and a scriptable CLI, built on the same engine.
            </p>
            <a
              href="https://github.com/elshadaghazade/diskgoup"
              className="mt-5 inline-flex items-center gap-2 text-sm text-muted transition-colors hover:text-ink"
              rel="noreferrer"
              target="_blank"
            >
              <GitHubMark />
              elshadaghazade/diskgoup
            </a>
          </div>

          {COLUMNS.map((column) => (
            <div key={column.title}>
              <h3 className="text-xs font-medium uppercase tracking-wider text-faint">
                {column.title}
              </h3>
              <ul className="mt-4 space-y-2.5">
                {column.links.map((link) => (
                  <li key={link.label}>
                    <a
                      href={link.href}
                      className="text-sm text-muted transition-colors hover:text-ink"
                      rel={link.href.startsWith('http') ? 'noreferrer' : undefined}
                      target={link.href.startsWith('http') ? '_blank' : undefined}
                    >
                      {link.label}
                    </a>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>

        <div className="mt-14 flex flex-col items-center justify-between gap-4 border-t border-line pt-8 text-xs text-faint sm:flex-row">
          <p>MIT licensed © DiskGOup contributors.</p>
          <p>Built in the open, for macOS, Windows and Linux.</p>
        </div>
      </div>
    </footer>
  )
}
