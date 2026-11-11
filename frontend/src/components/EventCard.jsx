import { Link } from 'react-router-dom'
import { Calendar, Clock, MapPin } from 'lucide-react'
import { formatDate, formatINR, formatTime, posterFallback } from '../services/format'

export default function EventCard({ event }) {
  const soldOut = event.total_seats > 0 && event.available_seats === 0
  return (
    <article className="card event-card">
      <Link to={`/events/${event.id}`} className="event-card-img" tabIndex={-1} aria-hidden="true">
        <img src={event.image_url || posterFallback} alt="" loading="lazy" onError={(e) => { e.currentTarget.src = posterFallback }} />
        <span className="badge badge-floating">{event.category}</span>
        {soldOut && <span className="badge badge-danger badge-floating-r">Sold out</span>}
      </Link>
      <div className="event-card-body">
        <h3 className="event-card-title"><Link to={`/events/${event.id}`}>{event.title}</Link></h3>
        <ul className="meta-list">
          <li><Calendar size={15} /> {formatDate(event.starts_at)}</li>
          <li><Clock size={15} /> {formatTime(event.starts_at)}</li>
          <li><MapPin size={15} /> {event.venue.name}, {event.venue.city}</li>
        </ul>
        <div className="event-card-foot">
          <div>
            <span className="muted small">Starting from</span>
            <div className="price">{event.min_price != null ? formatINR(event.min_price) : '—'}</div>
          </div>
          <Link to={`/events/${event.id}`} className="btn btn-primary btn-sm">View Details</Link>
        </div>
      </div>
    </article>
  )
}
