import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Proxy /api to the .NET API during development so the SPA can use same-origin paths.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:5038',
        changeOrigin: true,
      },
    },
  },
})
