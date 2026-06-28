import process from 'node:process'
import { defineConfig } from 'vite'
import { fileURLToPath, URL } from 'node:url'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// Backend origin for local `npm run dev`. The compose stack publishes the
// backend container on host port 8000 (docker-compose.yml: "8000:8000").
const BACKEND = process.env.VITE_DEV_BACKEND || 'http://localhost:8000'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  // Dev-only reverse proxy. Mirrors infra/nginx.conf so the app's relative
  // API paths (/auth, /tasks, /ws) reach the backend during `vite dev`.
  // Production is unaffected — there, nginx does this same routing.
  server: {
    proxy: {
      '/auth': { target: BACKEND, changeOrigin: true },
      '/tasks': { target: BACKEND, changeOrigin: true },
      '/ws': { target: BACKEND, changeOrigin: true, ws: true },
    },
  },
})
