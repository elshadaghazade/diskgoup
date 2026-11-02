// @ts-check
import { defineConfig } from 'astro/config';
import starlight from '@astrojs/starlight';

// Vercel exports the deployment's host during the build, so the canonical URLs
// and the sitemap point at the site itself instead of a hard-coded domain.
const vercelHost = process.env.VERCEL_PROJECT_PRODUCTION_URL || process.env.VERCEL_URL;

// https://astro.build/config
export default defineConfig({
	// The site is served from the root of the domain — no `base` path.
	site: vercelHost ? `https://${vercelHost}` : 'http://localhost:4321',
	integrations: [
		starlight({
			title: 'DiskGOup',
			description:
				'Cross-platform disk space analyzer and duplicate file finder for macOS, Linux and Windows.',
			// the app's own icon — the same donut chart the desktop app shows
			logo: {
				src: './src/assets/logo.svg',
				alt: 'DiskGOup',
			},
			// the custom 404 page lives in src/content/docs/404.md
			disable404Route: true,
			social: [
				{
					icon: 'github',
					label: 'GitHub',
					href: 'https://github.com/elshadaghazade/diskgoup',
				},
			],
			sidebar: [
				{
					label: 'Getting started',
					items: [
						{ label: 'Installation', slug: 'getting-started/installation' },
						{ label: 'Downloads', slug: 'getting-started/downloads' },
						{ label: 'Quick start', slug: 'getting-started/quick-start' },
						{ label: 'Where things are stored', slug: 'getting-started/paths' },
					],
				},
				{
					label: 'Guides',
					items: [
						{ label: 'Scanning', slug: 'guide/scanning' },
						{ label: 'Explore views', slug: 'guide/views' },
						{ label: 'Searching', slug: 'guide/search' },
						{ label: 'Finding duplicates', slug: 'guide/duplicates' },
						{ label: 'Cleaning up safely', slug: 'guide/cleanup' },
						{ label: 'Archives', slug: 'guide/archives' },
						{ label: 'Applications', slug: 'guide/applications' },
						{ label: 'Games', slug: 'guide/games' },
						{ label: 'Live monitor', slug: 'guide/monitor' },
						{ label: 'Snapshots', slug: 'guide/snapshots' },
						{ label: 'Reports', slug: 'guide/reports' },
					],
				},
				{
					label: 'Desktop app',
					items: [
						{ label: 'The desktop app', slug: 'desktop/overview' },
						{ label: 'Explore', slug: 'desktop/explore' },
						{ label: 'Search', slug: 'desktop/search' },
						{ label: 'Archives', slug: 'desktop/archives' },
						{ label: 'Duplicates', slug: 'desktop/duplicates' },
						{ label: 'Applications', slug: 'desktop/applications' },
						{ label: 'Games', slug: 'desktop/games' },
						{ label: 'Monitor', slug: 'desktop/monitor' },
						{ label: 'Snapshots', slug: 'desktop/snapshots' },
						{ label: 'Reports', slug: 'desktop/reports' },
					],
				},
				{
					label: 'Reference',
					items: [
						{ label: 'CLI reference', slug: 'reference/cli' },
						{ label: 'JSON-RPC protocol', slug: 'reference/json-rpc' },
						{ label: 'File kinds', slug: 'reference/file-kinds' },
						{ label: 'Protection rules', slug: 'reference/protection' },
						{ label: 'The scan index', slug: 'reference/scan-index' },
						{ label: 'Environment variables', slug: 'reference/environment' },
					],
				},
				{
					label: 'Development',
					items: [
						{ label: 'Architecture', slug: 'development/architecture' },
						{ label: 'The desktop app', slug: 'development/desktop' },
						{ label: 'Building and releasing', slug: 'development/building' },
						{ label: 'Contributing', slug: 'development/contributing' },
					],
				},
			],
		}),
	],
});
