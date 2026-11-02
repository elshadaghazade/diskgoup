import { Check, X } from 'lucide-react'

const ROWS = [
  { label: 'Price', them: 'Paid, per platform', us: 'Free, MIT licensed' },
  { label: 'Platforms', them: 'One operating system each', us: 'macOS, Windows and Linux' },
  { label: 'Automation', them: 'Point and click only', us: 'A scriptable CLI, JSON everywhere' },
  { label: 'Source', them: 'Closed', us: 'Open, and built in the open' },
  { label: 'Cleanup', them: 'A one-click delete button', us: 'Staged, reviewed, then to the recycle bin' },
  { label: 'Your data', them: 'On their machine, in their format', us: 'In a SQLite index you own' },
]

export default function WhySection() {
  return (
    <section className="border-t border-line/70 py-24">
      <div className="mx-auto max-w-5xl px-6">
        <div className="mx-auto max-w-2xl text-center">
          <p className="text-sm font-medium uppercase tracking-[0.18em] text-accent">Why it is free</p>
          <h2 className="mt-4 text-balance text-3xl font-bold tracking-tight text-ink sm:text-4xl">
            The same job, without the lock-in
          </h2>
          <p className="mt-4 text-base leading-relaxed text-muted">
            Disk-space analysers are a mature — mostly paid — market. The commercial tools do a good
            job, but they are closed-source, each one targets a single platform, and every one of
            them is GUI-only. This is the same work, open and cross-platform.
          </p>
        </div>

        <div className="mt-12 overflow-hidden rounded-2xl border border-line">
          <table className="w-full border-collapse text-left text-sm">
            <thead>
              <tr className="bg-elevated/60 text-xs uppercase tracking-wider text-faint">
                <th className="w-1/4 px-5 py-4 font-medium"> </th>
                <th className="px-5 py-4 font-medium">The usual tools</th>
                <th className="px-5 py-4 font-medium text-accent">DiskGOup</th>
              </tr>
            </thead>
            <tbody>
              {ROWS.map((row, index) => (
                <tr key={row.label} className={index % 2 ? 'bg-surface/40' : ''}>
                  <td className="px-5 py-4 font-medium text-ink">{row.label}</td>
                  <td className="px-5 py-4 text-muted">
                    <span className="flex items-start gap-2">
                      <X className="mt-0.5 size-4 shrink-0 text-faint" />
                      {row.them}
                    </span>
                  </td>
                  <td className="px-5 py-4 text-ink">
                    <span className="flex items-start gap-2">
                      <Check className="mt-0.5 size-4 shrink-0 text-accent" />
                      {row.us}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </section>
  )
}
