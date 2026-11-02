'use client'

import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from '@/components/ui/accordion'

const QUESTIONS = [
  {
    question: 'Is it really free?',
    answer:
      'Yes — DiskGOup is MIT licensed and free on every platform, with no paid tier and no account. The source is public, so nobody can put a price on it later without changing the licence in the open.',
  },
  {
    question: 'Do I need Python to use the command line?',
    answer:
      'Not on your machine. Every release ships a standalone binary that runs anywhere. If you prefer to work from the source, uv or pip installs it for you — but nothing forces you to.',
  },
  {
    question: 'Does it delete anything on its own?',
    answer:
      'No. A cleanup is staged, reviewed, validated and confirmed before anything moves, and the files end up in the recycle bin rather than being deleted outright. Protected paths — system folders, game data, the containers the operating system needs — can never be staged at all.',
  },
  {
    question: 'Why does macOS or Windows warn me about the download?',
    answer:
      'The project publishes no signing certificate, so the macOS .dmg and the Windows .exe are unsigned and not notarized. The operating system asks before it lets an unsigned build run. Whether to allow it is your decision and your responsibility — and you can verify the SHA-256 checksum or build the binary from source instead.',
  },
  {
    question: 'Can I use it on a server or in a script?',
    answer:
      'Yes. Every command speaks JSON, the scan index is a SQLite file you own, and nothing in the CLI needs a display. That is the same interface the desktop app drives.',
  },
  {
    question: 'How is this different from the paid analysers?',
    answer:
      'Those tools do good work, but they are closed-source, each one targets a single platform, and every one of them is GUI-only. DiskGOup does the same job with the source open, on macOS, Windows and Linux, with a scriptable CLI at the centre.',
  },
]

export default function Faq() {
  return (
    <section id="faq" className="border-t border-line/70 py-24">
      <div className="mx-auto grid max-w-6xl gap-12 px-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.6fr)]">
        <div>
          <p className="text-sm font-medium uppercase tracking-[0.18em] text-accent">Questions</p>
          <h2 className="mt-4 text-balance text-3xl font-bold tracking-tight text-ink sm:text-4xl">
            The things people ask first
          </h2>
          <p className="mt-4 text-base leading-relaxed text-muted">
            Something else on your mind? The documentation goes deeper — and the source is open, so
            you can read the answers in the code.
          </p>
          <a
            href="https://diskgoup.vercel.app/getting-started/quick-start/"
            className="mt-6 inline-block text-sm text-accent underline underline-offset-4"
            rel="noreferrer"
            target="_blank"
          >
            Read the quick start →
          </a>
        </div>

        <Accordion type="single" collapsible className="w-full">
          {QUESTIONS.map((item, index) => (
            <AccordionItem key={item.question} value={`item-${index}`}>
              <AccordionTrigger>{item.question}</AccordionTrigger>
              <AccordionContent>{item.answer}</AccordionContent>
            </AccordionItem>
          ))}
        </Accordion>
      </div>
    </section>
  )
}
