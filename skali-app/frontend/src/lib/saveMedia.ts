// Save an image/video to the device.
//  - Native (Capacitor Android/iOS): writes the file to the Documents directory
//    via @capacitor/filesystem when that plugin is present in the build.
//  - Web / preview: downloads via a blob <a download> link, falling back to
//    opening the media in a new tab when the fetch is blocked by CORS.
// Returns true on success. Throws only for unexpected failures.

function guessName(url: string): string {
  const clean = url.split('?')[0]
  const base = clean.split('/').pop() || ''
  if (base && /\.[a-z0-9]{2,5}$/i.test(base)) return base
  const ext = /\.(mp4|webm|mov)(\?|$)/i.test(url) ? 'mp4' : 'jpg'
  return `skali-${Date.now()}.${ext}`
}

function blobToBase64(blob: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const r = new FileReader()
    r.onloadend = () => resolve(String(r.result).split(',')[1] || '')
    r.onerror = reject
    r.readAsDataURL(blob)
  })
}

async function saveNative(url: string, name: string): Promise<boolean> {
  try {
    const core: any = await import('@capacitor/core')
    if (!core?.Capacitor?.isNativePlatform?.()) return false
    const fsSpec = '@capacitor/filesystem'
    const fsMod: any = await import(/* @vite-ignore */ fsSpec).catch(() => null)
    if (!fsMod?.Filesystem) return false
    const res = await fetch(url)
    const blob = await res.blob()
    const data = await blobToBase64(blob)
    await fsMod.Filesystem.writeFile({
      path: name,
      data,
      directory: fsMod.Directory?.Documents ?? 'DOCUMENTS',
      recursive: true,
    })
    return true
  } catch {
    return false
  }
}

export async function saveMedia(url: string, filename?: string): Promise<'saved' | 'opened'> {
  const name = filename || guessName(url)

  // 1) Native gallery/files save when running inside the app build.
  if (await saveNative(url, name)) return 'saved'

  // 2) Web: fetch -> blob -> download link (keeps the media off a new tab).
  try {
    const res = await fetch(url, { mode: 'cors' })
    if (!res.ok) throw new Error('fetch failed')
    const blob = await res.blob()
    const objUrl = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = objUrl
    a.download = name
    document.body.appendChild(a)
    a.click()
    a.remove()
    setTimeout(() => URL.revokeObjectURL(objUrl), 4000)
    return 'saved'
  } catch {
    // 3) CORS/offline fallback — open so the user can long-press to save.
    const a = document.createElement('a')
    a.href = url
    a.download = name
    a.target = '_blank'
    a.rel = 'noopener'
    document.body.appendChild(a)
    a.click()
    a.remove()
    return 'opened'
  }
}
