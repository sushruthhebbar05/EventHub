import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// In development the Vite server proxies API, uploaded images and WebSocket traffic to FastAPI,
// so the browser only ever talks to http://localhost:5173 (no CORS problems).
const backend = process.env.VITE_BACKEND_URL || 'http://localhost:8000'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': backend,
      '/static': backend,
      '/ws': { target: backend.replace(/^http/, 'ws'), ws: true },
    },
  },
})
