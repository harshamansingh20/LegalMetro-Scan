import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Dev: /api/* is proxied to the FastAPI backend, so no CORS setup is needed locally.
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': { target: process.env.API_TARGET || 'http://127.0.0.1:8000', rewrite: (p) => p.replace(/^\/api/, '') },
    },
  },
})
