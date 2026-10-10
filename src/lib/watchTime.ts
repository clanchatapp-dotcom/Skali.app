import { useEffect } from 'react'
import { api } from './api'

// Pings the backend every 30s while a viewer is watching a live stream (Creator Health watch time).
export function useWatchHeartbeat(liveId: string | undefined, active: boolean) {
  useEffect(() => {
    if (!liveId || !active) return
    const ping = () => api.watchHeartbeat(liveId).catch(() => {})
    ping()
    const t = setInterval(ping, 30000)
    return () => clearInterval(t)
  }, [liveId, active])
}
