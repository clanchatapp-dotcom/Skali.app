import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import '@livekit/components-styles'
import App from './App'
import { AuthProvider } from './lib/auth'
import { initGoogle } from './lib/nativeGoogle'
import { initStatusBar } from './lib/statusBar'
import { warmup } from './lib/api'
import './index.css'

initGoogle().catch(() => {})
initStatusBar().catch(() => {})
// Kick the backend awake the instant the app's JS loads (before React/auth even
// mounts), so a cold Render instance is already booting while the UI paints.
warmup()

// Visible fallback so a startup crash (bad config, JS error) is never a silent
// black screen — critical for the Android WebView where there's no dev console.
class ErrorBoundary extends React.Component<{ children: React.ReactNode }, { error: Error | null }> {
  constructor(props: any) { super(props); this.state = { error: null } }
  static getDerivedStateFromError(error: Error) { return { error } }
  render() {
    if (this.state.error) {
      return (
        <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 24, background: '#0b1020', color: '#e2e8f0', fontFamily: 'system-ui, sans-serif', textAlign: 'center' }}>
          <div style={{ maxWidth: 420 }}>
            <h1 style={{ fontSize: 20, marginBottom: 12 }}>Skali couldn't start</h1>
            <p style={{ opacity: 0.8, fontSize: 14, marginBottom: 12 }}>Something went wrong while loading the app.</p>
            <pre style={{ whiteSpace: 'pre-wrap', fontSize: 12, background: '#111827', padding: 12, borderRadius: 8, textAlign: 'left', overflow: 'auto' }}>{String(this.state.error?.message || this.state.error)}</pre>
            <button onClick={() => window.location.reload()} style={{ marginTop: 16, padding: '10px 18px', borderRadius: 8, background: '#6366f1', color: '#fff', border: 'none', fontSize: 14 }}>Reload</button>
          </div>
        </div>
      )
    }
    return this.props.children
  }
}

try {
  ReactDOM.createRoot(document.getElementById('root')!).render(
    <React.StrictMode>
      <ErrorBoundary>
        <BrowserRouter>
          <AuthProvider>
            <App />
          </AuthProvider>
        </BrowserRouter>
      </ErrorBoundary>
    </React.StrictMode>,
  )
} catch (e: any) {
  const root = document.getElementById('root')
  if (root) root.innerHTML = '<div style="min-height:100vh;display:flex;align-items:center;justify-content:center;padding:24px;background:#0b1020;color:#e2e8f0;font-family:system-ui,sans-serif;text-align:center"><div><h1 style="font-size:20px">Skali couldn\'t start</h1><pre style="white-space:pre-wrap;font-size:12px">' + String(e?.message || e) + '</pre></div></div>'
}
