import { Gamepad2, MessageSquare, Music, Palette, Camera, Trophy, Radio } from 'lucide-react'

export type LiveCategory = { key: string; label: string; icon: any; accent: string }

// Twitch-style categories — labels & icons mirror the backend LIVE_CATEGORIES keys.
export const LIVE_CATEGORIES: LiveCategory[] = [
  { key: 'gaming', label: 'Gaming', icon: Gamepad2, accent: 'text-violet-300' },
  { key: 'just_chatting', label: 'Just Chatting', icon: MessageSquare, accent: 'text-sky-300' },
  { key: 'music', label: 'Music', icon: Music, accent: 'text-emerald-300' },
  { key: 'creative', label: 'Creative', icon: Palette, accent: 'text-amber-300' },
  { key: 'irl', label: 'IRL', icon: Camera, accent: 'text-rose-300' },
  { key: 'sports', label: 'Sports', icon: Trophy, accent: 'text-orange-300' },
]

const BY_KEY: Record<string, LiveCategory> = Object.fromEntries(
  LIVE_CATEGORIES.map(c => [c.key, c]),
)

export const categoryOf = (key?: string): LiveCategory =>
  BY_KEY[key || 'just_chatting'] || { key: 'just_chatting', label: 'Just Chatting', icon: Radio, accent: 'text-sky-300' }

export const categoryLabel = (key?: string): string => categoryOf(key).label
