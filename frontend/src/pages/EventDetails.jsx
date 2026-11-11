import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { Calendar, Clock, MapPin, Ticket } from 'lucide-react'
import { eventsApi } from '../services/endpoints'
import { formatDate, formatINR, formatTime, posterFallback } from '../services/format'
import { ErrorBox, PageLoader } from '../components/Feedback'

export default function EventDetails() {
  const { id } = useParams()
  const [event, setEvent] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    eventsApi.get(id).then(setEvent).catch((e) => setError(e.response?.status === 404 ? 'This event does not exist or is not public.' : 'Could not load the event.'))
  }, [id])

  if (error) return <div className="container page"><ErrorBox message={error} /></div>
  if (!event) return <PageLoader />

  const bookable = event.status === 'APPROVED' && event.available_seats > 0
  return (
    <div className="container page">
      <div className="detail-hero">
        <img src={event.image_url || posterFallback} alt="" onError={(e) => { e.currentTarget.src = posterFallback }} />
        <div className="detail-hero-shade" />
        <div className="detail-hero-text">
          <span className="badge">{event.category}</span>
          <h1>{event.title}</h1>
        </div>
      </div>

      <div className="detail-grid">
        <div>
          {event.status !== 'APPROVED' && <div className="alert alert-info">This event is <strong>{event.status.toLowerCase()}</strong>{event.status === 'PENDING' ? ' and waiting for admin approval.' : '.'}</div>}
          <h2>About this event</h2>
          <p className="prose">{event.description || 'Details coming soon.'}</p>
          <h2>Ticket types</h2>
          <div className="section-cards">
            {event.sections.map((s) => (
              <div key={s.name} className="card section-card">
                <strong>{s.name}</strong>
                <span className="price">{formatINR(s.price)}</span>
                <span className={s.available === 0 ? 'danger small' : 'muted small'}>{s.available === 0 ? 'Sold out' : `${s.available} of ${s.total} left`}</span>
              </div>
            ))}
          </div>
        </div>
        <aside className="card booking-box">
          <ul className="meta-list meta-lg">
            <li><Calendar size={18} /> {formatDate(event.starts_at)}</li>
            <li><Clock size={18} /> {formatTime(event.starts_at)} IST</li>
            <li><MapPin size={18} /> <span>{event.venue.name}<br /><span className="muted small">{event.venue.address}, {event.venue.city}</span></span></li>
          </ul>
          <div className="booking-price"><span className="muted small">Tickets from</span><div className="price price-lg">{event.min_price != null ? formatINR(event.min_price) : '—'}</div></div>
          {bookable ? (
            <Link to={`/events/${event.id}/seats`} className="btn btn-primary btn-block"><Ticket size={18} /> Select seats</Link>
          ) : (
            <button className="btn btn-primary btn-block" disabled>{event.status === 'APPROVED' ? 'Sold out' : 'Not on sale'}</button>
          )}
          <p className="small muted center">{event.available_seats} of {event.total_seats} seats available</p>
        </aside>
      </div>
    </div>
  )
}
