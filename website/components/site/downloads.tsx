import { Apple, Download, Monitor, Package, ShieldAlert, Terminal } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'

const RELEASES = 'https://github.com/elshadaghazade/diskgoup/releases/latest/download'

const PLATFORMS = [
  {
    name: 'macOS',
    icon: Apple,
    desktop: [
      { label: 'Apple silicon', file: 'DiskGOup-macOS-arm64.dmg' },
      { label: 'Intel', file: 'DiskGOup-macOS-x64.dmg' },
    ],
    portable: [
      { label: 'Apple silicon', file: 'DiskGOup-macOS-arm64.zip' },
      { label: 'Intel', file: 'DiskGOup-macOS-x64.zip' },
    ],
    cli: [
      { label: 'Apple silicon', file: 'diskgoup-cli-macos-arm64.tar.gz' },
      { label: 'Intel', file: 'diskgoup-cli-macos-x64.tar.gz' },
    ],
    unsigned: true,
  },
  {
    name: 'Windows',
    icon: Monitor,
    desktop: [{ label: 'x64', file: 'DiskGOup-Windows-x64.exe' }],
    portable: [{ label: 'x64', file: 'DiskGOup-Windows-portable-x64.exe' }],
    cli: [{ label: 'x64', file: 'diskgoup-cli-windows-x64.zip' }],
    unsigned: true,
  },
  {
    name: 'Linux',
    icon: Terminal,
    desktop: [{ label: 'x64', file: 'DiskGOup-Linux-x64.AppImage' }],
    portable: [{ label: 'x64', file: 'DiskGOup-Linux-x64.tar.gz' }],
    cli: [
      { label: 'x64', file: 'diskgoup-cli-linux-x64.tar.gz' },
      { label: 'arm64', file: 'diskgoup-cli-linux-arm64.tar.gz' },
    ],
    unsigned: false,
  },
]

export default function Downloads() {
  return (
    <section id="download" className="border-t border-line/70 py-24">
      <div className="mx-auto max-w-6xl px-6">
        <div className="max-w-2xl">
          <p className="text-sm font-medium uppercase tracking-[0.18em] text-accent">Downloads</p>
          <h2 className="mt-4 text-balance text-3xl font-bold tracking-tight text-ink sm:text-4xl">
            Take it with you
          </h2>
          <p className="mt-4 text-base leading-relaxed text-muted">
            Every release ships a standalone CLI binary and the desktop app, built by the
            project&rsquo;s own CI. The CLI needs no Python on your machine, and the app bundles
            the very same binary — so it is self-contained too. Each platform also gets a{' '}
            <strong className="font-medium text-ink">portable</strong> build: no installer, no
            admin rights — unpack it and run it from any folder, or from a USB stick.
          </p>
        </div>

        <div className="mt-12 grid gap-5 md:grid-cols-3">
          {PLATFORMS.map((platform) => (
            <div
              key={platform.name}
              className="flex flex-col rounded-2xl border border-line bg-surface/70 p-6"
            >
              <div className="flex items-center gap-3">
                <span className="grid size-9 place-items-center rounded-xl border border-line bg-elevated text-muted">
                  <platform.icon className="size-4.5" />
                </span>
                <h3 className="text-base font-semibold text-ink">{platform.name}</h3>
              </div>

              <div className="mt-6">
                <div className="text-xs font-medium uppercase tracking-wider text-faint">
                  Desktop app
                </div>
                <div className="mt-3 flex flex-col gap-2">
                  {platform.desktop.map((item) => (
                    <Button key={item.file} asChild variant="outline" size="sm" className="justify-between">
                      <a href={`${RELEASES}/${item.file}`} rel="noreferrer" target="_blank">
                        <span className="flex items-center gap-2">
                          <Download className="size-3.5" />
                          {item.label}
                        </span>
                      </a>
                    </Button>
                  ))}
                </div>
              </div>

              <div className="mt-6">
                <div className="text-xs font-medium uppercase tracking-wider text-faint">
                  Portable — no install
                </div>
                <div className="mt-3 flex flex-col gap-2">
                  {platform.portable.map((item) => (
                    <a
                      key={item.file}
                      href={`${RELEASES}/${item.file}`}
                      rel="noreferrer"
                      target="_blank"
                      className="flex items-center gap-2 rounded-full px-1 text-[13px] text-muted transition-colors hover:text-accent"
                    >
                      <Package className="size-3.5" />
                      {item.label}
                      <span className="truncate text-[11px] text-faint">{item.file}</span>
                    </a>
                  ))}
                </div>
                <p className="mt-2 px-1 text-[11px] leading-relaxed text-faint">
                  Unpack it and run the app from wherever you like — a folder, a USB stick.
                </p>
              </div>

              <div className="mt-6">
                <div className="text-xs font-medium uppercase tracking-wider text-faint">CLI</div>
                <div className="mt-3 flex flex-col gap-2">
                  {platform.cli.map((item) => (
                    <a
                      key={item.file}
                      href={`${RELEASES}/${item.file}`}
                      rel="noreferrer"
                      target="_blank"
                      className="flex items-center gap-2 rounded-full px-1 text-[13px] text-muted transition-colors hover:text-accent"
                    >
                      <Terminal className="size-3.5" />
                      {item.label}
                      <span className="truncate text-[11px] text-faint">{item.file}</span>
                    </a>
                  ))}
                </div>
              </div>

              <div className="mt-6 flex-1" />

              {platform.unsigned ? (
                <Badge variant="outline" className="self-start">
                  <ShieldAlert className="size-3.5 text-accent" />
                  Unsigned build
                </Badge>
              ) : (
                <Badge variant="outline" className="self-start">
                  No gatekeeper warning
                </Badge>
              )}
            </div>
          ))}
        </div>

        <div className="mt-6 rounded-2xl border border-accent/25 bg-accent/[0.06] p-6">
          <h3 className="flex items-center gap-2 text-sm font-semibold text-ink">
            <ShieldAlert className="size-4 text-accent" />
            The macOS and Windows builds are not code-signed
          </h3>
          <div className="mt-3 grid gap-6 text-sm leading-relaxed text-muted lg:grid-cols-2">
            <p>
              The project publishes no signing certificate, so Gatekeeper and SmartScreen warn on
              the first launch. The warning is the operating system asking, not the app failing —
              and whether to allow an unsigned build on your own machine is your decision, and your
              responsibility. On macOS, right-click the app in the mounted{' '}
              <code className="font-mono text-[13px] text-accent">.dmg</code> and choose{' '}
              <strong className="text-ink">Open</strong>; on Windows, choose{' '}
              <strong className="text-ink">More info</strong> and then{' '}
              <strong className="text-ink">Run anyway</strong>. The Linux AppImage is unaffected.
              The portable copies are asked about in exactly the same way — the check follows
              the code, not the file it arrives in.
            </p>
            <p>
              If you would rather not allow an unsigned binary at all, two other roads lead to the
              same program: verify the download against the SHA-256 checksums shipped with every
              release, or build it from the source. Both are one command away —{' '}
              <a
                href="https://diskgoup-docs.vercel.app/getting-started/downloads/"
                className="text-accent underline underline-offset-4"
                rel="noreferrer"
                target="_blank"
              >
                the downloads page
              </a>{' '}
              has the details.
            </p>
          </div>
        </div>
      </div>
    </section>
  )
}
