import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Bell } from 'lucide-react'
import { api } from '../lib/api'

// Messages header pill that opens Activity, with an unread count.
export default function ActivityPill() {
  const nav = useNavigate()
  const [count, setCount] = useState(0)

  useEffect(() => {
    const load = () => api.unread().then((u: any) => setCount(Number(u?.activity || 0))).catch(() => {})
    load()
    const id = setInterval(load, 20000)
    return () => clearInterval(id)
  }, [])

  return (
    <button onClick={() => nav('/activity')} data-testid="messages-activity-pill"
      className="ml-auto relative flex items-center gap-1.5 px-3.5 py-1.5 rounded-full bg-panel border border-edge text-sm font-semibold text-slate-200 hover:text-white hover:border-brand/40 transition-colors">
      <Bell className="h-4 w-4 text-brand" /> Activity
      {count > 0 && (
        <span data-testid="messages-activity-count"
          className="min-w-[18px] h-[18px] px-1 rounded-full bg-rose-500 text-white text-[10px] grid place-items-center font-bold">
          {count > 99 ? '99+' : count}
        </span>
      )}
    </button>
  )
}
