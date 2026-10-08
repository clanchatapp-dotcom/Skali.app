// Phase 5 — per-user display prefs applied app-wide via CSS variables on <html>.
import { setStatusBarTheme } from './statusBar'

export type ThemePrefs = { theme?: string; accent?: string; font_size?: string }

// Each accent maps to space-separated RGB triples used by the Tailwind tokens
// (bg-brand / text-brand / border-brand) which are defined as rgb(var(--brand) / <alpha>).
export const ACCENTS: Record<string, { label: string; hex: string; rgb: string; d600: string; d700: string }> = {
  violet: { label: 'Violet', hex: '#6d5efc', rgb: '109 94 252', d600: '91 77 240', d700: '74 61 214' },
  blue: { label: 'Blue', hex: '#3b82f6', rgb: '59 130 246', d600: '37 99 235', d700: '29 78 216' },
  emerald: { label: 'Emerald', hex: '#10b981', rgb: '16 185 129', d600: '5 150 105', d700: '4 120 87' },
  rose: { label: 'Rose', hex: '#f43f5e', rgb: '244 63 94', d600: '225 29 72', d700: '190 18 60' },
  amber: { label: 'Amber', hex: '#f59e0b', rgb: '245 158 11', d600: '217 119 6', d700: '180 83 9' },
  cyan: { label: 'Cyan', hex: '#06b6d4', rgb: '6 182 212', d600: '8 145 178', d700: '14 116 144' },
}

const FONT_PX: Record<string, string> = { small: '15px', normal: '16px', large: '18px' }

export function applyTheme(p: ThemePrefs = {}) {
  const root = document.documentElement
  const isLight = p.theme === 'light'
  root.classList.toggle('light', isLight)
  const a = ACCENTS[p.accent || 'violet'] || ACCENTS.violet
  root.style.setProperty('--brand', a.rgb)
  root.style.setProperty('--brand-600', a.d600)
  root.style.setProperty('--brand-700', a.d700)
  root.style.fontSize = FONT_PX[p.font_size || 'normal'] || FONT_PX.normal
  setStatusBarTheme(isLight).catch(() => {})
}
