import { useEffect, useState } from 'react'

const ROWS = 7
const COLS = 12
const key = (r, c) => `${r}-${c}`

// Decorative only: a miniature seat map whose seats change state, hinting at the live updates in the real app.
export default function HeroSeats() {
  const [overrides, setOverrides] = useState({})

  useEffect(() => {
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return undefined
    const id = setInterval(() => {
      const r = Math.floor(Math.random() * ROWS)
      const c = Math.floor(Math.random() * COLS)
      const next = ['held', 'booked', 'available'][Math.floor(Math.random() * 3)]
      setOverrides((o) => ({ ...o, [key(r, c)]: next }))
    }, 700)
    return () => clearInterval(id)
  }, [])

  return (
    <div className="hero-seats" aria-hidden="true">
      <div className="stage stage-mini"><span>STAGE</span></div>
      {Array.from({ length: ROWS }, (_, r) => (
        <div key={r} className="hero-seat-row" style={{ paddingInline: `${Math.abs(r - 3) * 4}px` }}>
          {Array.from({ length: COLS }, (_, c) => {
            const base = (r * 7 + c * 3) % 11 === 0 ? 'booked' : 'available'
            return <i key={c} className={`seat seat-static seat-${overrides[key(r, c)] || base}`} />
          })}
        </div>
      ))}
    </div>
  )
}
