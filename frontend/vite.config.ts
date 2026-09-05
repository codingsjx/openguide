import { fileURLToPath } from 'node:url'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// Root resolved from this config's own location so Vite works regardless of
// the process working directory (launch.json invokes vite.js directly).
const root = fileURLToPath(new URL('.', import.meta.url))

// https://vite.dev/config/
export default defineConfig({
  root,
  plugins: [react()],
  // Vite 8 runs pre-bundling via esbuild/rollup; ensure node is resolvable
  // when spawned with an absolute node.exe (PATH may not include it yet).
  server: {
    host: '127.0.0.1',
    port: 5173,
    proxy: {
      // Dev proxy to the FastAPI backend. In prod, serve built assets behind
      // the same origin (see docker-compose) and VITE_API_BASE is not needed.
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
})
