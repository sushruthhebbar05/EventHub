import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { organiserApi, eventsApi } from '../services/endpoints'
import { errorMessage } from '../services/api'
import { formatDate, formatTime, posterFallback } from '../services/format'
import { useToast } from '../context/ToastContext'
import { Empty, ErrorBox, PageLoader } from '../components/Feedback'

export default function ManageEvents() {
  const toast = useToast()
  const [events, setEvents] = useState(null)
  const [error, setError] = useState('')
  const load = useCallback(() => { organiserApi.events().then((r) => setEvents(r.items)).catch((e) => setError(errorMessage(e))) }, [])
  useEffect(() => { load() }, [load])

  const act = async (fn, ok) => {
    try { await fn(); toast.success(ok); load() } catch (e) { toast.error(errorMessage(e)) }
  }

  if (error) return <div className="container page"><ErrorBox message={error} /></div>
  if (!events) return <PageLoader />
  return (
    <div className="container page">
      <div className="page-head"><h1>Manage events</h1><Link to="/organiser/events/new" className="btn btn-primary">Create event</Link></div>
      {events.length === 0 ? <Empty title="No events yet">Create your first event to start selling tickets.</Empty> : (
        <div className="stack">{events.map((e) => (
          <div key={e.id} className="card manage-row">
            <img src={e.image_url || posterFallback} alt="" onError={(ev) => { ev.currentTarget.src = posterFallback }} />
            <div className="manage-info">
              <h3><Link to={`/events/${e.id}`}>{e.title}</Link></h3>
              <p className="muted small">{formatDate(e.starts_at)} · {formatTime(e.starts_at)} · {e.venue.name}, {e.venue.city}</p>
              <p className="small"><span className={`status status-${e.status.toLowerCase()}`}>{e.status.toLowerCase()}</span> · {e.total_seats - e.available_seats} of {e.total_seats} seats taken</p>
              {e.status === 'PENDING' && <p className="small muted">Waiting for admin approval - it is not public yet.</p>}
            </div>
            <div className="row-actions">
              <Link to={`/organiser/events/${e.id}/edit`} className="btn btn-outline btn-sm">Edit</Link>
              {e.status !== 'CANCELLED' && <button className="btn btn-outline btn-sm" onClick={() => window.confirm('Cancel this event? It will stop selling tickets.') && act(() => eventsApi.update(e.id, { cancel: true }), 'Event cancelled')}>Cancel event</button>}
              <button className="btn btn-danger btn-sm" onClick={() => window.confirm('Delete this event permanently?') && act(() => eventsApi.remove(e.id), 'Event deleted')}>Delete</button>
            </div>
          </div>
        ))}</div>
      )}
    </div>
  )
}
