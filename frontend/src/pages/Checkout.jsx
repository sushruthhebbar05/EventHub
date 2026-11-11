import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { Calendar, MapPin } from 'lucide-react'
import { bookingsApi } from '../services/endpoints'
import { errorMessage } from '../services/api'
import { formatDate, formatINR, formatTime, seatLabel } from '../services/format'
import { useToast } from '../context/ToastContext'
import CountdownBadge from '../components/CountdownBadge'
import { ErrorBox, PageLoader, Spinner } from '../components/Feedback'

export default function Checkout() {
  const { bookingId } = useParams()
  const navigate = useNavigate()
  const toast = useToast()
  const [booking, setBooking] = useState(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [expired, setExpired] = useState(false)

  useEffect(() => {
    bookingsApi.get(bookingId).then((b) => {
      if (b.status === 'CONFIRMED') navigate(`/booking-success/${b.id}`, { replace: true })
      else setBooking(b)
    }).catch((e) => setError(errorMessage(e, 'Booking not found')))
  }, [bookingId, navigate])

  const changeSeats = async () => {
    setBusy(true)
    try {
      if (booking.status === 'PENDING_PAYMENT') await bookingsApi.cancel(booking.id)
    } catch { /* already expired: fine */ }
    navigate(`/events/${booking.event.id}/seats`)
  }

  if (error) return <div className="container page"><ErrorBox message={error} /></div>
  if (!booking) return <PageLoader />

  const dead = expired || booking.status !== 'PENDING_PAYMENT'
  return (
    <div className="container page narrow">
      <h1>Review your order</h1>
      <div className="card order">
        <div className="order-head">
          <h2>{booking.event.title}</h2>
          <ul className="meta-list">
            <li><Calendar size={15} /> {formatDate(booking.event.starts_at)} · {formatTime(booking.event.starts_at)}</li>
            <li><MapPin size={15} /> {booking.event.venue_name}, {booking.event.city}</li>
          </ul>
        </div>
        <ul className="summary-list">
          {booking.items.map((i) => <li key={i.id}><span>{seatLabel(i)}</span><strong>{formatINR(i.price)}</strong></li>)}
        </ul>
        <div className="summary-total"><span>Total payable</span><strong>{formatINR(booking.total_amount)}</strong></div>
        <p className="small muted">Booking reference {booking.reference}</p>
      </div>

      {dead ? (
        <div className="alert alert-error">
          Your seat hold has expired and the seats were released. <Link to={`/events/${booking.event.id}/seats`}>Choose seats again</Link>
        </div>
      ) : (
        <>
          <CountdownBadge expiresAt={booking.expires_at} onExpire={() => { setExpired(true); toast.error('Your hold expired') }} />
          <div className="actions">
            <button className="btn btn-outline" onClick={changeSeats} disabled={busy}>Change seats</button>
            <Link to={`/payment/${booking.id}`} className="btn btn-primary">Continue to payment</Link>
          </div>
        </>
      )}
      {busy && <Spinner />}
    </div>
  )
}
