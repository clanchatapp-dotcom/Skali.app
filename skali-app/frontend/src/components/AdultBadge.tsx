// Small no-18 shield shown next to adult-content creators' names, EVERYWHERE they
// appear (feed, profile, DMs, activity, member lists) — exactly like staff RoleBadge.
// It flags the account, not the individual post, so it shows even in tier 1 & 2 where
// there's no NSFW content.

export default function AdultBadge({ nsfw, size = 16, className = '' }: { nsfw?: boolean | null; size?: number; className?: string }) {
  if (!nsfw) return null
  return (
    <img
      src="/no18.png"
      alt="18+ only"
      title="Adult content creator (18+)"
      width={size}
      height={size}
      style={{ width: size, height: size }}
      className={`inline-block object-contain align-text-bottom shrink-0 ${className}`}
    />
  )
}
