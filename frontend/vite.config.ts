import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Live data always comes from the Render backend (override with SKALI_API_URL).
const RENDER_BACKEND = process.env.SKALI_API_URL || 'https://clanchatapp-backend.onrender.com'

export default defineConfig({
  plugins: [react()],
  envPrefix: ['VITE_', 'REACT_APP_'],
  define: {
    'import.meta.env.REACT_APP_BACKEND_URL': JSON.stringify(RENDER_BACKEND),
  },
  // Prefer TS sources over leftover CRA template files (App.js / index.js).
  resolve: { extensions: ['.tsx', '.ts', '.jsx', '.mjs', '.js', '.mts', '.json'] },
  server: {
    host: '0.0.0.0',
    port: 3000,
    strictPort: true,
    allowedHosts: true as any,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8001',
        changeOrigin: true,
        ws: true,
      },
    },
    hmr: { clientPort: 443 },
    watch: { ignored: ['**/android/**', '**/dist/**', '**/build/**'] },
  },
})
