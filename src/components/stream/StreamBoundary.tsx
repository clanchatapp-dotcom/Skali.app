import { Component, ReactNode } from 'react'

// Keeps any Phase 2 streaming/chat/VOD failure contained to its own panel.
export default class StreamBoundary extends Component<{ children: ReactNode; label?: string }, { failed: boolean }> {
  state = { failed: false }

  static getDerivedStateFromError() {
    return { failed: true }
  }

  componentDidCatch(e: unknown) {
    console.warn('[stream] panel crashed', e)
  }

  render() {
    if (this.state.failed) {
      return (
        <div className="rounded-2xl border border-edge bg-panel p-4 text-sm text-slate-400" data-testid="stream-boundary-error">
          {this.props.label || 'Streaming tools'} hit a problem. The rest of Skali keeps working — reload to try again.
        </div>
      )
    }
    return this.props.children
  }
}
