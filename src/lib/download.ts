import { Capacitor } from '@capacitor/core'
import { Filesystem, Directory } from '@capacitor/filesystem'
import { Share } from '@capacitor/share'

const EXT: Record<string, string> = { image: 'jpg', video: 'mp4', audio: 'webm' }

const fileName = (url: string, type: string) => {
  const base = decodeURIComponent(url.split('?')[0].split('/').pop() || '')
  const m = base.match(/\.([a-z0-9]{2,5})$/i)
  return `skali-${Date.now()}.${m ? m[1].toLowerCase() : EXT[type] || 'bin'}`
}

const toBase64 = (blob: Blob) => new Promise<string>((res, rej) => {
  const r = new FileReader()
  r.onload = () => res(String(r.result).split(',')[1] || '')
  r.onerror = rej
  r.readAsDataURL(blob)
})

// Saves a media file to the device. Returns a short message for the user.
const BLOB_EXT: Record<string, string> = { 'image/jpeg': 'jpg', 'image/png': 'png', 'image/webp': 'webp', 'image/gif': 'gif' }

// `getBlob` lets the caller supply the file itself (e.g. a watermarked copy from the backend).
export async function downloadMedia(url: string, type: string, getBlob?: () => Promise<Blob>): Promise<string> {
  let supplied: Blob | null = null
  let name = fileName(url, type)
  if (getBlob) {
    supplied = await getBlob()
    const ext = BLOB_EXT[supplied.type]
    if (ext) name = name.replace(/\.[a-z0-9]{2,5}$/i, '') + '.' + ext
  }
  if (Capacitor.isNativePlatform()) {
    const data = await toBase64(supplied ?? await (await fetch(url)).blob())
    try {
      await Filesystem.writeFile({ path: `Skali/${name}`, data, directory: Directory.Documents, recursive: true })
      return 'Saved to Documents/Skali'
    } catch {
      const f = await Filesystem.writeFile({ path: name, data, directory: Directory.Cache })
      await Share.share({ title: 'Save media', url: f.uri })
      return ''
    }
  }
  try {
    const blob = supplied ?? await (await fetch(url, { mode: 'cors' })).blob()
    const href = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = href; a.download = name
    document.body.appendChild(a); a.click(); a.remove()
    setTimeout(() => URL.revokeObjectURL(href), 4000)
    return 'Downloaded'
  } catch {
    window.open(url, '_blank', 'noopener')
    return 'Opened in a new tab'
  }
}
