import { useEffect, useRef, useState } from 'react'

const MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']
const MIN_AGE = 13
const TOO_YOUNG_MSG = `You must be ${MIN_AGE}+ to join Skali. Come back when you're a little older!`

// Days in month; month is 1-12. Leap years handled by Date rollover.
export const daysInMonth = (month: number, year?: number) =>
  new Date(year || 2000, month, 0).getDate()

const pad = (n: number) => String(n).padStart(2, '0')

const parse = (v: string) => {
  const [y, m, d] = (v || '').split('-').map(Number)
  return { y: y || 0, m: m || 0, d: d || 0 }
}

const ageOn = (y: number, m: number, d: number, now: Date) => {
  const hadBirthday = now.getMonth() + 1 > m || (now.getMonth() + 1 === m && now.getDate() >= d)
  return now.getFullYear() - y - (hadBirthday ? 0 : 1)
}

const selectCls = 'bg-ink border border-edge rounded-xl px-3 py-3 outline-none focus:border-brand transition text-slate-200 min-w-0'

export default function DobPicker({ value, onChange, required, testId = 'dob' }: {
  value: string
  onChange: (v: string) => void
  required?: boolean
  testId?: string
}) {
  const init = parse(value)
  const [d, setD] = useState(init.d)
  const [m, setM] = useState(init.m)
  const [y, setY] = useState(init.y)
  const yearRef = useRef<HTMLSelectElement>(null)

  const now = new Date()
  const thisYear = now.getFullYear()
  const years = Array.from({ length: 121 }, (_, i) => thisYear - i)
  const maxDay = m ? daysInMonth(m, y || undefined) : 31

  const complete = !!(d && m && y && d <= daysInMonth(m, y))
  const tooYoung = !!y && (thisYear - y < MIN_AGE || (complete && ageOn(y, m, d, now) < MIN_AGE))

  // Clamp the day when month/year change (e.g. 31 Jan -> Feb becomes 28/29).
  useEffect(() => {
    if (d > maxDay) setD(maxDay)
  }, [maxDay])

  useEffect(() => {
    yearRef.current?.setCustomValidity(tooYoung ? `You must be ${MIN_AGE}+` : '')
    onChange(complete && !tooYoung ? `${y}-${pad(m)}-${pad(d)}` : '')
  }, [d, m, y])

  return (
    <div>
      <div className="grid grid-cols-[1fr_1.6fr_1.2fr] gap-2" data-testid={`${testId}-picker`}>
        <select required={required} value={d || ''} onChange={e => setD(Number(e.target.value))}
          className={selectCls} aria-label="Day" data-testid={`${testId}-day-select`}>
          <option value="" disabled>Day</option>
          {Array.from({ length: 31 }, (_, i) => i + 1).map(n => (
            <option key={n} value={n} disabled={n > maxDay} hidden={n > maxDay}>{n}</option>
          ))}
        </select>
        <select required={required} value={m || ''} onChange={e => setM(Number(e.target.value))}
          className={selectCls} aria-label="Month" data-testid={`${testId}-month-select`}>
          <option value="" disabled>Month</option>
          {MONTHS.map((name, i) => <option key={name} value={i + 1}>{name}</option>)}
        </select>
        <select ref={yearRef} required={required} value={y || ''} onChange={e => setY(Number(e.target.value))}
          className={`${selectCls} ${tooYoung ? 'border-amber-400/70' : ''}`} aria-label="Year" data-testid={`${testId}-year-select`}>
          <option value="" disabled>Year</option>
          {years.map(n => <option key={n} value={n}>{n}</option>)}
        </select>
      </div>
      {tooYoung && (
        <p role="alert" className="text-amber-300 text-xs mt-2 px-1" data-testid={`${testId}-too-young-msg`}>
          {TOO_YOUNG_MSG}
        </p>
      )}
    </div>
  )
}
