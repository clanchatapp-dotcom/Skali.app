// Inline coloured shield badge shown next to staff members' names.
//   super_admin (green) · co_admin (pink) · moderator (red) · first_tester (blue)
// Images live in /public/badges and have transparent backgrounds (dark-theme friendly).

export const ROLE_META: Record<string, { label: string; src: string; color: string }> = {
  super_admin: { label: 'Super Admin', src: '/badges/role-super_admin.png', color: 'text-green-400' },
  co_admin: { label: 'Co-Admin', src: '/badges/role-co_admin.png', color: 'text-pink-400' },
  moderator: { label: 'Moderator', src: '/badges/role-moderator.png', color: 'text-red-400' },
  first_tester: { label: 'First Tester', src: '/badges/role-first_tester.png', color: 'text-blue-400' },
}

export default function RoleBadge({ role, size = 16, className = '' }: { role?: string | null; size?: number; className?: string }) {
  if (!role) return null
  const meta = ROLE_META[role]
  if (!meta) return null
  return (
    <img
      src={meta.src}
      alt={meta.label}
      title={meta.label}
      width={size}
      height={size}
      style={{ width: size, height: size }}
      className={`inline-block object-contain align-text-bottom shrink-0 ${className}`}
    />
  )
}
