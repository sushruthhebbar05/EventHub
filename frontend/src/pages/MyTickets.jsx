import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { QrCode } from 'lucide-react'
import { bookingsApi } from '../services/endpoints'
import { errorMessage } from '../services/api'
import { formatDate, formatINR, formatTime, posterFallback, seatLabel } from '../services/format'
import { useToast } from '../context/ToastContext'
import { DownloadTicketButton, QRImage } from '../components/TicketQR'
import { Empty, ErrorBox, PageLoader } from '../components/Feedback'

function BookingCard({ booking, onChanged }) {
  const toast = useToast()
  const [openId, setOpenId] = useState(null)
  const [busy, setBusy] = useState(false)
  const upcoming = new Date(booking.event.starts_at) > new Date()

  const cancel = async () => {
    if (!window.confirm('Cancel this booking? Your seats will be released and the amount refunded.')) return
    setBusy(true)
    try {
      await bookingsApi.cancel(booking.id)
      toast.success('Booking cancelled and refunded')
      onChanged()
    } catch (e) {
      toast.error(errorMessage(e, 'Could not cancel'))
    } finally { setBusy(false) }
  }

  return (
    <article className="card booking-card">
      <img src={booking.event.image_url || posterFallback} alt="" onError={(e) => { e.currentTarget.src = posterFallback }} />
      <div className="booking-card-body">
        <div className="booking-card-top">
          <div>
            <h3><Link to={`/events/${booking.event.id}`}>{booking.event.title}</Link></h3>
            <p className="muted small">{formatDate(booking.event.starts_at)} · {formatTime(booking.event.starts_at)} · {booking.event.venue_name}, {booking.event.city}</p>
          </div>
          <span className={`status status-${booking.status.toLowerCase()}`}>{booking.status.replace('_', ' ').toLowerCase()}</span>
        </div>
        <p className="small muted">Ref {booking.reference} · {formatINR(booking.total_amount)} · {booking.items.length} ticket{booking.items.length > 1 ? 's' : ''}</p>

        {booking.status === 'CONFIRMED' && booking.items.map((i) => (
          <div key={i.id} className="ticket-row">
            <div className="ticket-row-head">
              <span>{seatLabel(i)} {i.ticket.checked_in && <span className="badge badge-muted">used</span>}</span>
              <span className="row-actions">
                <button className="btn btn-ghost btn-sm" onClick={() => setOpenId(openId === i.id ? null : i.id)}><QrCode size={16} /> {openId === i.id ? 'Hide QR' : 'Show QR'}</button>
                <DownloadTicketButton ticketId={i.ticket.id} />
              </span>
            </div>
            {openId === i.id && <div className="ticket-row-qr"><QRImage ticketId={i.ticket.id} size={180} /></div>}
          </div>
        ))}

        <div className="actions left">
          {booking.status === 'PENDING_PAYMENT' && <Link to={`/checkout/${booking.id}`} className="btn btn-primary btn-sm">Resume checkout</Link>}
          {booking.status === 'CONFIRMED' && upcoming && <button className="btn btn-outline btn-sm" onClick={cancel} disabled={busy}>Cancel booking</button>}
        </div>
      </div>
    </article>
  )
}

export default function MyTickets() {
  const [bookings, setBookings] = useState(null)
  const [error, setError] = useState('')
  const [tab, setTab] = useState('upcoming')

  const load = useCallback(() => { bookingsApi.list().then(setBookings).catch((e) => setError(errorMessage(e))) }, [])
  useEffect(() => { load() }, [load])

  if (error) return <div className="container page"><ErrorBox message={error} onRetry={load} /></div>
  if (!bookings) return <PageLoader />

  const now = new Date()
  const groups = {
    upcoming: bookings.filter((b) => ['CONFIRMED', 'PENDING_PAYMENT'].includes(b.status) && new Date(b.event.starts_at) > now),
    past: bookings.filter((b) => b.status === 'CONFIRMED' && new Date(b.event.starts_at) <= now),
    cancelled: bookings.filter((b) => ['CANCELLED', 'EXPIRED'].includes(b.status)),
  }
  return (
    <div className="container page">
      <h1>My tickets</h1>
      <div className="tabs" role="tablist">
        {Object.keys(groups).map((k) => (
          <button key={k} role="tab" aria-selected={tab === k} className={tab === k ? 'tab active' : 'tab'} onClick={() => setTab(k)}>
            {k[0].toUpperCase() + k.slice(1)} <span className="count">{groups[k].length}</span>
          </button>
        ))}
      </div>
      {groups[tab].length === 0 ? (
        <Empty title="Nothing here yet">{tab === 'upcoming' ? <>Find something to go to in <Link to="/events">Events</Link>.</> : 'No bookings in this list.'}</Empty>
      ) : (
        <div className="stack">{groups[tab].map((b) => <BookingCard key={b.id} booking={b} onChanged={load} />)}</div>
      )}
    </div>
  )
}
