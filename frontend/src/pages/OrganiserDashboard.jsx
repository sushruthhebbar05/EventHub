import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { BadgeIndianRupee, CalendarDays, ScanLine, Ticket, Users } from 'lucide-react'
import { organiserApi } from '../services/endpoints'
import { errorMessage } from '../services/api'
import { formatDate, formatINR, formatShortDate } from '../services/format'
import { ErrorBox, PageLoader, Spinner } from '../components/Feedback'

function Stat({ icon: Icon, label, value }) {
  return <div className="card stat"><Icon size={20} className="accent" /><div className="stat-value">{value}</div><div className="muted small">{label}</div></div>
}

function BookingsPanel({ eventId }) {
  const [rows, setRows] = useState(null)
  useEffect(() => { organiserApi.bookings(eventId).then(setRows).catch(() => setRows([])) }, [eventId])
  if (!rows) return <div className="panel"><Spinner /></div>
  if (!rows.length) return <div className="panel muted">No bookings yet.</div>
  return (
    <div className="panel table-wrap">
      <table className="table">
        <thead><tr><th>Ref</th><th>Attendee</th><th>Seats</th><th>Amount</th><th>Status</th></tr></thead>
        <tbody>{rows.map((r) => (
          <tr key={r.booking_id}><td>{r.reference}</td><td>{r.attendee_name}<br /><span className="muted small">{r.attendee_email}</span></td><td>{r.seats.join(', ')}</td><td>{formatINR(r.amount)}</td><td><span className={`status status-${r.status.toLowerCase()}`}>{r.status.toLowerCase()}</span></td></tr>
        ))}</tbody>
      </table>
    </div>
  )
}

export default function OrganiserDashboard() {
  const [summary, setSummary] = useState(null)
  const [stats, setStats] = useState(null)
  const [open, setOpen] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    Promise.all([organiserApi.summary(), organiserApi.stats()]).then(([s, st]) => { setSummary(s); setStats(st) }).catch((e) => setError(errorMessage(e)))
  }, [])

  if (error) return <div className="container page"><ErrorBox message={error} /></div>
  if (!summary) return <PageLoader />

  return (
    <div className="container page">
      <div className="page-head">
        <h1>Organiser dashboard</h1>
        <div className="actions left">
          <Link to="/organiser/events/new" className="btn btn-primary">Create event</Link>
          <Link to="/organiser/events" className="btn btn-outline">Manage events</Link>
          <Link to="/organiser/check-in" className="btn btn-outline"><ScanLine size={16} /> Entry check-in</Link>
        </div>
      </div>
      <div className="grid grid-stats">
        <Stat icon={CalendarDays} label="Total events" value={summary.total_events} />
        <Stat icon={Ticket} label="Tickets sold" value={summary.tickets_sold} />
        <Stat icon={Users} label="Bookings" value={summary.total_bookings} />
        <Stat icon={BadgeIndianRupee} label="Total revenue" value={formatINR(summary.total_revenue)} />
      </div>

      <h2>Sales by event</h2>
      {stats.length === 0 ? <p className="muted">You haven't created any events yet.</p> : (
        <div className="stack">
          {stats.map((s) => {
            const pct = (n) => (s.total_seats ? (n / s.total_seats) * 100 : 0)
            return (
              <div key={s.event_id} className="card event-stat">
                <div className="event-stat-top">
                  <div><strong>{s.title}</strong><div className="muted small">{formatDate(s.starts_at)} · <span className={`status status-${s.status.toLowerCase()}`}>{s.status.toLowerCase()}</span></div></div>
                  <div className="event-stat-rev"><strong>{formatINR(s.revenue)}</strong><div className="muted small">{s.booked} sold</div></div>
                </div>
                <div className="bar" role="img" aria-label={`${s.booked} booked, ${s.held} held, ${s.available} available`}>
                  <span className="bar-booked" style={{ width: `${pct(s.booked)}%` }} /><span className="bar-held" style={{ width: `${pct(s.held)}%` }} />
                </div>
                <div className="small muted">{s.booked} booked · {s.held} held · {s.available} available of {s.total_seats}</div>
                <button className="btn btn-ghost btn-sm" onClick={() => setOpen(open === s.event_id ? null : s.event_id)}>{open === s.event_id ? 'Hide bookings' : 'View bookings'}</button>
                {open === s.event_id && <BookingsPanel eventId={s.event_id} />}
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
