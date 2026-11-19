import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    strictPort: true,
    proxy: {
      // In docker compose the backend is the `web` service, not localhost.
      '/api': process.env.API_PROXY_TARGET ?? 'http://localhost:8000',
    },
  },
})
