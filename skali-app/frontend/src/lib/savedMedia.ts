// A lightweight, device-local record of media the user has saved/downloaded.
// Downloads happen at the OS/browser level, so we keep our own list here (in
// localStorage) to power the in-app "Saved" area.

export type SavedItem = { url: string; type: string; at: number }

const KEY = 'cc_saved_media'
const CHANGED = 'cc-saved-changed'

export function getSaved(): SavedItem[] {
  try {
    const raw = localStorage.getItem(KEY)
    const list = raw ? JSON.parse(raw) : []
    return Array.isArray(list) ? list : []
  } catch {
    return []
  }
}

export function recordSaved(url: string, type: string = 'image') {
  if (!url) return
  try {
    const list = getSaved().filter(i => i.url !== url)
    list.unshift({ url, type: type || 'image', at: Date.now() })
    localStorage.setItem(KEY, JSON.stringify(list.slice(0, 300)))
    window.dispatchEvent(new Event(CHANGED))
  } catch {
    // Ignore storage errors (private mode / quota).
  }
}

export function removeSaved(url: string) {
  try {
    localStorage.setItem(KEY, JSON.stringify(getSaved().filter(i => i.url !== url)))
    window.dispatchEvent(new Event(CHANGED))
  } catch {
    // Ignore.
  }
}

export function clearSaved() {
  try {
    localStorage.removeItem(KEY)
    window.dispatchEvent(new Event(CHANGED))
  } catch {
    // Ignore.
  }
}

export const SAVED_CHANGED_EVENT = CHANGED
