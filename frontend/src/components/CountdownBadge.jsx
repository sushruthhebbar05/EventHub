import { Timer } from 'lucide-react'
import { useCountdown } from '../hooks/useCountdown'

export default function CountdownBadge({ expiresAt, onExpire }) {
  const { secondsLeft, label } = useCountdown(expiresAt, onExpire)
  if (secondsLeft == null) return null
  return (
    <div className={`countdown ${secondsLeft <= 60 ? 'countdown-urgent' : ''}`} role="timer" aria-live="off">
      <Timer size={18} />
      <div>
        <div className="countdown-time">{label}</div>
        <div className="small muted">Seats held for you</div>
      </div>
    </div>
  )
}
