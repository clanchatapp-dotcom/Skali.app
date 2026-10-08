// Tiny dependency-free toast. Renders a fixed pill at the bottom of the screen
// and auto-dismisses. Works from anywhere (including inside portals/modals)
// because it appends directly to <body>.

type ToastKind = 'success' | 'info' | 'error'

const COLORS: Record<ToastKind, string> = {
  success: 'rgba(16,185,129,0.95)', // emerald
  info: 'rgba(30,41,59,0.95)',      // slate
  error: 'rgba(225,29,72,0.95)',    // rose
}

export function showToast(message: string, kind: ToastKind = 'success') {
  if (typeof document === 'undefined') return

  const el = document.createElement('div')
  el.textContent = message
  el.setAttribute('data-testid', 'app-toast')
  el.style.cssText = [
    'position:fixed',
    'left:50%',
    'bottom:calc(5.5rem + env(safe-area-inset-bottom))',
    'transform:translateX(-50%) translateY(10px)',
    'z-index:2147483000',
    'max-width:86vw',
    'padding:10px 16px',
    'border-radius:9999px',
    'color:#fff',
    'font:600 13px/1.3 ui-sans-serif,system-ui,sans-serif',
    'box-shadow:0 10px 30px rgba(0,0,0,.35)',
    'opacity:0',
    'transition:opacity .2s ease, transform .2s ease',
    'pointer-events:none',
    'text-align:center',
    `background:${COLORS[kind]}`,
    'backdrop-filter:blur(6px)',
  ].join(';')

  document.body.appendChild(el)
  requestAnimationFrame(() => {
    el.style.opacity = '1'
    el.style.transform = 'translateX(-50%) translateY(0)'
  })

  setTimeout(() => {
    el.style.opacity = '0'
    el.style.transform = 'translateX(-50%) translateY(10px)'
    setTimeout(() => el.remove(), 250)
  }, 2200)
}
