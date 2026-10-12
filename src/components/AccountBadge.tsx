import { BadgeCheck, Star } from 'lucide-react'

// Small inline badge shown next to a name.
//  - `verified` (identity-checked via Yoti/OneID) -> blue tick, highest priority.
//    Fans use this to see who is identity-verified. (Staff/tier badges are separate
//    and will be reworked later.)
//  - premium -> gold star, verified tier -> blue check.
// Renders nothing for free accounts, or when a staff role shield is already shown.
export default function AccountBadge({ type, role, verified, size = 15, className = '' }: {
  type?: string | null
  role?: string | null
  verified?: boolean | null
  size?: number
  className?: string
}) {
  if (verified) {
    return <BadgeCheck title="Identity verified" width={size} height={size} style={{ width: size, height: size }}
      className={`inline-block align-text-bottom shrink-0 text-sky-400 fill-sky-400/15 ${className}`} data-testid="verified-badge" />
  }
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
