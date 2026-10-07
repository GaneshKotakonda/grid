import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/health': 'http://127.0.0.1:8000',
      '/grid': 'http://127.0.0.1:8000',
      '/simulate': 'http://127.0.0.1:8000',
      '/results': 'http://127.0.0.1:8000',
      '/benchmarks': {
        target: 'http://127.0.0.1:8000',
        bypass(req, res) {
          res.setHeader('Vary', 'Accept');
          if (req.headers.accept?.includes('text/html')) return '/index.html';
        },
      },
    },
  },
})
