import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// The renderer is loaded from the filesystem by Electron in production, so
// every asset reference must be relative.
export default defineConfig({
  plugins: [react()],
  base: './',
  build: {
    outDir: 'dist',
    emptyOutDir: true,
    target: 'es2022',
    sourcemap: true,
  },
  server: {
    port: 5173,
    strictPort: true,
  },
})
