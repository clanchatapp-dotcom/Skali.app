import { BadgeCheck, Star } from 'lucide-react'

// Small inline tier badge: premium (gold star) or verified (blue check).
// Renders nothing for free accounts, or when a staff role shield is already shown
// (a role implies verified, so we avoid doubling up).
export default function AccountBadge({ type, role, size = 15, className = '' }: {
  type?: string | null
  role?: string | null
  size?: number
  className?: string
}) {
  if (role) return null
  if (type === 'premium') {
    return <Star title="Premium" width={size} height={size} style={{ width: size, height: size }}
      className={`inline-block align-text-bottom shrink-0 text-amber-400 fill-amber-400 ${className}`} />
  }
  if (type === 'verified') {
    return <BadgeCheck title="Verified" width={size} height={size} style={{ width: size, height: size }}
      className={`inline-block align-text-bottom shrink-0 text-sky-400 ${className}`} />
  }
  return null
}

export const ACCOUNT_META: Record<string, { label: string; color: string }> = {
  free: { label: 'Free', color: 'text-slate-400' },
  premium: { label: 'Premium', color: 'text-amber-400' },
  verified: { label: 'Verified', color: 'text-sky-400' },
}
