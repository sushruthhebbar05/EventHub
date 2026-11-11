import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { CheckCircle2 } from 'lucide-react'
import { bookingsApi } from '../services/endpoints'
import { errorMessage } from '../services/api'
import { formatDate, formatINR, formatTime, seatLabel } from '../services/format'
import { DownloadTicketButton, QRImage } from '../components/TicketQR'
import { ErrorBox, PageLoader } from '../components/Feedback'

export default function BookingSuccess() {
  const { bookingId } = useParams()
  const [booking, setBooking] = useState(null)
  const [error, setError] = useState('')
  useEffect(() => { bookingsApi.get(bookingId).then(setBooking).catch((e) => setError(errorMessage(e))) }, [bookingId])

  if (error) return <div className="container page"><ErrorBox message={error} /></div>
  if (!booking) return <PageLoader />
  if (booking.status !== 'CONFIRMED') return <div className="container page"><div className="alert alert-error">This booking is {booking.status.toLowerCase().replace('_', ' ')}.</div></div>

  return (
    <div className="container page narrow">
      <div className="success-head">
        <CheckCircle2 size={44} className="ok" />
        <h1>You're going!</h1>
        <p className="muted">Booking <strong>{booking.reference}</strong> · {formatINR(booking.total_amount)} paid</p>
        <p>{booking.event.title} · {formatDate(booking.event.starts_at)} · {formatTime(booking.event.starts_at)}<br /><span className="muted">{booking.event.venue_name}, {booking.event.city}</span></p>
      </div>
      <div className="ticket-list">
        {booking.items.map((i) => (
          <div key={i.id} className="card ticket">
            <div className="ticket-info">
              <span className="badge">E-ticket</span>
              <h3>{seatLabel(i)}</h3>
              <p className="muted small">Show this QR code at the entrance. Each code works once.</p>
              <DownloadTicketButton ticketId={i.ticket.id} />
            </div>
            <QRImage ticketId={i.ticket.id} />
          </div>
        ))}
      </div>
      <div className="actions"><Link to="/tickets" className="btn btn-primary">View all my tickets</Link><Link to="/events" className="btn btn-outline">Browse more events</Link></div>
    </div>
  )
}
