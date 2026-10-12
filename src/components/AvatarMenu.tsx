import { useState } from 'react'
import { createPortal } from 'react-dom'
import { useNavigate } from 'react-router-dom'
import { Loader2, PlayCircle, User } from 'lucide-react'
import { api } from '../lib/api'
import { Avatar } from '../lib/ui'
import { StoryViewer, StoryGroup } from './Stories'

type U = { id?: string; handle: string; display_name?: string; avatar_url?: string | null }

// Tap a profile picture -> small menu with View profile / View story (story only when active).
export default function AvatarMenu({ user, size, testId }: { user: U; size?: number; testId?: string }) {
  const nav = useNavigate()
  const [open, setOpen] = useState(false)
  const [group, setGroup] = useState<StoryGroup | null | undefined>(undefined)
  const [viewing, setViewing] = useState(false)

  const tap = async (e: React.MouseEvent) => {
    e.preventDefault(); e.stopPropagation()
    setOpen(true); setGroup(undefined)
    try {
      const r = await api.storiesOfUser(user.handle)
      setGroup(r.stories?.length ? { user: r.user, is_self: r.is_self, all_viewed: false, stories: r.stories } : null)
    } catch { setGroup(null) }
  }

  const close = () => setOpen(false)

  return (
    <>
      <span role="button" tabIndex={0} onClick={tap} data-testid={testId || `avatar-menu-${user.handle}`}
        className="inline-block shrink-0 cursor-pointer rounded-full">
        <Avatar id={user.id || user.handle} name={user.display_name || user.handle} url={user.avatar_url} size={size} />
      </span>

      {open && createPortal(
        <div className="fixed inset-0 z-[88] bg-black/70 backdrop-blur grid place-items-end sm:place-items-center"
          onClick={e => { e.stopPropagation(); close() }} data-testid="avatar-menu-sheet">
          <div className="bg-panel border border-edge rounded-t-2xl sm:rounded-2xl w-full max-w-sm p-2 pb-[calc(0.5rem+env(safe-area-inset-bottom))]" onClick={e => e.stopPropagation()}>
            <div className="px-4 pt-2 pb-1 text-xs text-slate-500 truncate">{user.display_name} · #{user.handle}</div>
            <button onClick={() => { close(); nav(`/u/${user.handle}`) }} data-testid="avatar-menu-view-profile"
              className="w-full flex items-center gap-3 px-4 py-3.5 rounded-xl hover:bg-white/5 text-left text-white">
              <User className="h-5 w-5 text-slate-300" /> View profile
            </button>
            {group === undefined && (
              <div className="flex items-center gap-3 px-4 py-3.5 text-slate-500 text-sm"><Loader2 className="h-4 w-4 animate-spin" /> Checking for a story…</div>
            )}
            {group && (
              <button onClick={() => { close(); setViewing(true) }} data-testid="avatar-menu-view-story"
                className="w-full flex items-center gap-3 px-4 py-3.5 rounded-xl hover:bg-white/5 text-left text-white">
                <PlayCircle className="h-5 w-5 text-brand" /> View story
              </button>
            )}
            <button onClick={close} data-testid="avatar-menu-cancel"
              className="w-full px-4 py-3 rounded-xl text-slate-400 hover:bg-white/5 text-center">Cancel</button>
          </div>
        </div>,
        document.body
      )}

      {viewing && group && <StoryViewer groups={[group]} startGroup={0} onClose={() => setViewing(false)} />}
    </>
  )
}
