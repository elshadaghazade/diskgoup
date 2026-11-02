import type { Metadata } from 'next'
import { Inter, JetBrains_Mono } from 'next/font/google'
import { siteUrl } from '@/lib/utils'
import './globals.css'
import './demo.css'
import './demo-overrides.css'

const inter = Inter({
  subsets: ['latin'],
  variable: '--font-inter',
  display: 'swap',
})

const mono = JetBrains_Mono({
  subsets: ['latin'],
  variable: '--font-mono-jet',
  display: 'swap',
})

const description =
  'DiskGOup is a free, open-source disk space analyzer and duplicate finder for macOS, ' +
  'Windows and Linux — with a desktop GUI and a scriptable CLI. See exactly where your ' +
  'disk space went, find duplicate files, and clean up what you approve.'

export const metadata: Metadata = {
  metadataBase: new URL(siteUrl),
  title: {
    default: 'DiskGOup — Take Control of Your Disk Space. For Free.',
    template: '%s · DiskGOup',
  },
  description,
  applicationName: 'DiskGOup',
  keywords: [
    'free disk space analyzer',
    'open source disk cleaner',
    'cross-platform disk analyzer',
    'duplicate file finder CLI',
    'disk usage analyzer macOS Windows Linux',
    'treemap disk analyzer',
    'DiskGOup',
  ],
  authors: [{ name: 'DiskGOup contributors' }],
  creator: 'DiskGOup',
  alternates: { canonical: '/' },
  openGraph: {
    type: 'website',
    url: '/',
    siteName: 'DiskGOup',
    title: 'DiskGOup — Take Control of Your Disk Space. For Free.',
    description,
  },
  twitter: {
    card: 'summary_large_image',
    title: 'DiskGOup — Take Control of Your Disk Space. For Free.',
    description,
  },
  robots: { index: true, follow: true },
  icons: {
    icon: '/icon.svg',
  },
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${inter.variable} ${mono.variable}`}>
      <body className="min-h-screen antialiased">{children}</body>
    </html>
  )
}
