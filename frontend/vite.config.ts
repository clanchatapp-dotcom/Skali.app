import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

// Live data comes from the Render backend (override with SKALI_API_URL), EXACTLY
// as in the original config. Production/APK builds (`vite build`, used by
// `cap:sync`) must NEVER pick up a local .env, otherwise the APK would ship
// pointing at a preview URL. Only the local dev server (serve) is allowed to
// read REACT_APP_BACKEND_URL from .env so the Emergent preview can talk to the
// local backend.
const RENDER_BACKEND = process.env.SKALI_API_URL || 'https://clanchatapp-backend.onrender.com'

export default defineConfig(({ command, mode }) => {
  let backend = RENDER_BACKEND
  if (command === 'serve') {
    const env = loadEnv(mode, process.cwd(), ['VITE_', 'REACT_APP_'])
    backend = env.REACT_APP_BACKEND_URL || RENDER_BACKEND
  }

  return {
    plugins: [react()],
    envPrefix: ['VITE_', 'REACT_APP_'],
    define: {
      'import.meta.env.REACT_APP_BACKEND_URL': JSON.stringify(backend),
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
  }
})
