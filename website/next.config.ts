import type { NextConfig } from 'next'

const nextConfig: NextConfig = {
  reactStrictMode: true,
  // The demo's data file is large and never changes between builds.
  async headers() {
    return [
      {
        source: '/demo.json',
        headers: [{ key: 'Cache-Control', value: 'public, max-age=3600' }],
      },
    ]
  },
}

export default nextConfig
