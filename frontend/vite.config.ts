import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/yaml':   'http://localhost:5000',
      '/run':    'http://localhost:5000',
      '/status': 'http://localhost:5000',
      '/output': 'http://localhost:5000',
      '/pngs':   'http://localhost:5000',
    },
  },
  build: {
    outDir: '../frontend_dist',
  },
})
