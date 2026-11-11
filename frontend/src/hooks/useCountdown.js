import { useEffect, useRef, useState } from 'react'

/** Counts down to an ISO timestamp. Calls onExpire once when it reaches zero. */
export function useCountdown(expiresAt, onExpire) {
  const [left, setLeft] = useState(() => (expiresAt ? Math.max(0, Math.floor((new Date(expiresAt) - Date.now()) / 1000)) : null))
  const cb = useRef(onExpire)
  cb.current = onExpire

  useEffect(() => {
    if (!expiresAt) {
      setLeft(null)
      return
    }
    let fired = false
    const tick = () => {
      const s = Math.max(0, Math.ceil((new Date(expiresAt) - Date.now()) / 1000))
      setLeft(s)
      if (s === 0 && !fired) {
        fired = true
        cb.current?.()
      }
    }
    tick()
    const id = setInterval(tick, 500)
    return () => clearInterval(id)
  }, [expiresAt])

  const label = left == null ? '' : `${String(Math.floor(left / 60)).padStart(2, '0')}:${String(left % 60).padStart(2, '0')}`
  return { secondsLeft: left, label }
}
