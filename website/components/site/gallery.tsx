const SHOTS = [
  {
    file: '/app/02-explore-treemap.png',
    alt: 'The treemap of a scanned disk, every folder drawn as a rectangle sized by its space',
    title: 'Treemap',
    body: 'The whole disk as one picture — folders drawn to scale, coloured by what is inside them.',
  },
  {
    file: '/app/11-safe-to-clean.png',
    alt: 'The safe-to-clean scope listing the caches and logs of the scan',
    title: 'Safe to clean',
    body: 'The caches and logs the operating system regenerates, staged for review instead of deleted on the spot.',
  },
  {
    file: '/app/15-duplicates.png',
    alt: 'The duplicates section listing identical files grouped by hash',
    title: 'Duplicates',
    body: 'Identical content found by SHA-256 and an exact byte compare, with the extra copies grouped.',
  },
  {
    file: '/app/20-reports.png',
    alt: 'The reports section with the weekly HTML report and the CSV export',
    title: 'Reports',
    body: 'A weekly HTML report and a file-type CSV — the numbers, written down for you.',
  },
]

export default function Gallery() {
  return (
    <section className="border-t border-line/70 py-24">
      <div className="mx-auto max-w-6xl px-6">
        <div className="flex flex-col justify-between gap-6 sm:flex-row sm:items-end">
          <div className="max-w-2xl">
            <p className="text-sm font-medium uppercase tracking-[0.18em] text-accent">The window</p>
            <h2 className="mt-4 text-balance text-3xl font-bold tracking-tight text-ink sm:text-4xl">
              Nine sections, one scan
            </h2>
            <p className="mt-4 text-base leading-relaxed text-muted">
              Explore, Search, Archives, Duplicates, Applications, Games, Monitor, Snapshots and
              Reports — all reading the same result set instead of touching the disk again.
            </p>
          </div>
        </div>

        <div className="mt-12 grid gap-5 sm:grid-cols-2">
          {SHOTS.map((shot) => (
            <figure
              key={shot.file}
              className="overflow-hidden rounded-2xl border border-line bg-surface/60 transition-colors hover:border-edge"
            >
              <img
                src={shot.file}
                alt={shot.alt}
                width={1280}
                height={725}
                loading="lazy"
                className="w-full border-b border-line bg-surface object-cover"
              />
              <figcaption className="p-5">
                <h3 className="text-sm font-semibold text-ink">{shot.title}</h3>
                <p className="mt-1.5 text-sm leading-relaxed text-muted">{shot.body}</p>
              </figcaption>
            </figure>
          ))}
        </div>
      </div>
    </section>
  )
}
