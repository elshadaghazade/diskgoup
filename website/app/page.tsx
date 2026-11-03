import CliSection from '@/components/site/cli-section'
import DemoSection from '@/components/site/demo-section'
import Downloads from '@/components/site/downloads'
import Faq from '@/components/site/faq'
import Features from '@/components/site/features'
import Footer from '@/components/site/footer'
import Gallery from '@/components/site/gallery'
import Header from '@/components/site/header'
import Hero from '@/components/site/hero'
import WhySection from '@/components/site/why-section'
import { siteUrl } from '@/lib/utils'

const DESCRIPTION =
  'DiskGOup is a free, open-source disk space analyzer and duplicate finder for macOS, ' +
  'Windows and Linux — with a desktop GUI and a scriptable CLI.'

const FAQ = [
  {
    question: 'Is it really free?',
    answer:
      'Yes — DiskGOup is MIT licensed and free on every platform, with no paid tier and no account.',
  },
  {
    question: 'Do I need Python to use the command line?',
    answer: 'Not on your machine. Every release ships a standalone binary that runs anywhere.',
  },
  {
    question: 'Does it delete anything on its own?',
    answer:
      'No. A cleanup is staged, reviewed, validated and confirmed before anything moves, and the ' +
      'files end up in the recycle bin rather than being deleted outright.',
  },
  {
    question: 'Why does macOS or Windows warn me about the download?',
    answer:
      'The project publishes no signing certificate, so the macOS .dmg and the Windows .exe are ' +
      'unsigned and not notarized. Whether to allow an unsigned build on your own machine is your ' +
      'decision, and your responsibility. The portable copies are asked about in the same way — ' +
      'the check follows the code, not the file it arrives in.',
  },
  {
    question: 'Can I use it on a server or in a script?',
    answer:
      'Yes. Every command speaks JSON, the scan index is a SQLite file you own, and nothing in ' +
      'the CLI needs a display.',
  },
  {
    question: 'How is this different from the paid analysers?',
    answer:
      'Those tools do good work, but they are closed-source, each one targets a single platform, ' +
      'and every one of them is GUI-only. DiskGOup does the same job with the source open, on ' +
      'macOS, Windows and Linux, with a scriptable CLI at the centre.',
  },
]

export default function Page() {
  const jsonLd = {
    '@context': 'https://schema.org',
    '@type': 'SoftwareApplication',
    name: 'DiskGOup',
    alternateName: 'DiskGOup',
    description: DESCRIPTION,
    url: siteUrl,
    applicationCategory: 'SystemApplication',
    operatingSystem: 'macOS, Windows, Linux',
    softwareVersion: '0.1.4',
    license: 'https://opensource.org/licenses/MIT',
    isAccessibleForFree: true,
    offers: {
      '@type': 'Offer',
      price: '0',
      priceCurrency: 'USD',
    },
    featureList: [
      'Cross-platform disk space analyzer',
      'Duplicate file finder with SHA-256 verification',
      'Treemap, sunburst, flame graph, bubbles and mind map views',
      'Staged and reviewed cleanup',
      'Scriptable CLI with JSON output',
    ],
  }

  const faqJsonLd = {
    '@context': 'https://schema.org',
    '@type': 'FAQPage',
    mainEntity: FAQ.map((item) => ({
      '@type': 'Question',
      name: item.question,
      acceptedAnswer: { '@type': 'Answer', text: item.answer },
    })),
  }

  return (
    <>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
      />
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(faqJsonLd) }}
      />

      <Header />
      <main>
        <Hero />
        <Features />
        <DemoSection />
        <Gallery />
        <CliSection />
        <WhySection />
        <Downloads />
        <Faq />
      </main>
      <Footer />
    </>
  )
}
