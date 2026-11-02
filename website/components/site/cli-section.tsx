import { GitHubMark } from '@/components/site/github-mark'
import { Button } from '@/components/ui/button'

const LINES: { prompt?: boolean; text: string; dim?: boolean }[] = [
  { prompt: true, text: 'diskgoup scan ~/ --json | jq ".files"' },
  { text: '218431', dim: true },
  { prompt: true, text: 'diskgoup sizes ~/ --limit 4' },
  { text: 'SIZE      PATH                          KIND', dim: true },
  { text: '38.4 GB   ~/Movies                      video', dim: true },
  { text: '12.1 GB   ~/Library/Caches              cache', dim: true },
  { text: '9.7 GB    ~/Applications                application', dim: true },
  { text: '4.2 GB    ~/Projects/website/node_modules code', dim: true },
  { prompt: true, text: 'diskgoup duplicates ~/ --json | jq ".total_reclaimable"' },
  { text: '2147483648', dim: true },
  { prompt: true, text: 'diskgoup cleanup stage ~/Downloads/old.dmg' },
  { text: 'Staged 1 item · 812.4 MB · nothing has been removed', dim: true },
]

export default function CliSection() {
  return (
    <section id="cli" className="border-t border-line/70 py-24">
      <div className="mx-auto grid max-w-6xl gap-12 px-6 lg:grid-cols-2 lg:items-center">
        <div>
          <p className="text-sm font-medium uppercase tracking-[0.18em] text-accent">The CLI is the product</p>
          <h2 className="mt-4 text-balance text-3xl font-bold tracking-tight text-ink sm:text-4xl">
            The desktop app is a front-end for the command line
          </h2>
          <p className="mt-4 text-base leading-relaxed text-muted">
            DiskGOup starts <code className="rounded bg-elevated px-1.5 py-0.5 font-mono text-[13px] text-accent">diskgoup serve</code> as a
            child process and asks it questions over JSON-RPC. Every number in the window was
            measured by the same Python code the shell uses — so if you can do it in the app, you
            can do it in a script, and the other way round.
          </p>
          <div className="mt-7 flex flex-wrap gap-3">
            <Button asChild variant="outline">
              <a
                href="https://diskgoup.vercel.app/reference/cli/"
                rel="noreferrer"
                target="_blank"
              >
                Read the command reference
              </a>
            </Button>
            <Button asChild variant="ghost">
              <a href="https://github.com/elshadaghazade/diskgoup" rel="noreferrer" target="_blank">
                <GitHubMark />
                Clone the source
              </a>
            </Button>
          </div>
        </div>

        <div className="overflow-hidden rounded-2xl border border-edge bg-surface shadow-[0_30px_80px_-40px_rgba(0,0,0,0.9)]">
          <div className="flex items-center gap-2 border-b border-line bg-elevated px-4 py-2.5">
            <span className="size-3 rounded-full bg-[#ff5f57]" />
            <span className="size-3 rounded-full bg-[#febc2e]" />
            <span className="size-3 rounded-full bg-[#28c840]" />
            <span className="ml-3 text-[11px] text-faint">zsh — diskgoup</span>
          </div>
          <div className="overflow-x-auto p-5 font-mono text-[12.5px] leading-relaxed">
            {LINES.map((line, index) => (
              <div key={index} className="whitespace-pre">
                {line.prompt ? (
                  <>
                    <span className="text-good">$</span> <span className="text-ink">{line.text}</span>
                  </>
                ) : (
                  <span className={line.dim ? 'text-faint' : 'text-ink'}>{line.text}</span>
                )}
              </div>
            ))}
          </div>
        </div>
      </div>
    </section>
  )
}
