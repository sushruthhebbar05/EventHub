import { useCallback, useEffect, useState } from 'react'
import { adminApi } from '../services/endpoints'
import { errorMessage } from '../services/api'
import { formatDate, formatINR } from '../services/format'
import { useToast } from '../context/ToastContext'
import { useAuth } from '../context/AuthContext'
import { ErrorBox, PageLoader } from '../components/Feedback'

export default function AdminDashboard() {
  const toast = useToast()
  const { user: me } = useAuth()
  const [stats, setStats] = useState(null)
  const [events, setEvents] = useState([])
  const [users, setUsers] = useState([])
  const [q, setQ] = useState('')
  const [error, setError] = useState('')

  const load = useCallback(() => {
    Promise.all([adminApi.stats(), adminApi.events(), adminApi.users(q || undefined)])
      .then(([s, e, u]) => { setStats(s); setEvents(e.items); setUsers(u) }).catch((err) => setError(errorMessage(err)))
  }, [q])
  useEffect(() => { load() }, [load])

  const act = async (fn, ok) => { try { await fn(); toast.success(ok); load() } catch (e) { toast.error(errorMessage(e)) } }

  if (error) return <div className="container page"><ErrorBox message={error} /></div>
  if (!stats) return <PageLoader />
  const pending = events.filter((e) => e.status === 'PENDING')

  return (
    <div className="container page">
      <h1>Admin dashboard</h1>
      <div className="grid grid-stats">
        {[['Users', stats.users_total], ['Events', stats.events_total], ['Pending approval', stats.events_pending], ['Tickets sold', stats.tickets_sold], ['Confirmed bookings', stats.bookings_confirmed], ['Revenue', formatINR(stats.revenue)]].map(([l, v]) => (
          <div key={l} className="card stat"><div className="stat-value">{v}</div><div className="muted small">{l}</div></div>
        ))}
      </div>

      <h2>Events awaiting approval</h2>
      {pending.length === 0 ? <p className="muted">Nothing to review.</p> : (
        <div className="stack">{pending.map((e) => (
          <div key={e.id} className="card manage-row">
            <div className="manage-info"><h3>{e.title}</h3><p className="muted small">{formatDate(e.starts_at)} · {e.venue.name}, {e.venue.city} · {e.total_seats} seats</p></div>
            <div className="row-actions">
              <button className="btn btn-primary btn-sm" onClick={() => act(() => adminApi.approve(e.id), 'Event approved')}>Approve</button>
              <button className="btn btn-danger btn-sm" onClick={() => act(() => adminApi.reject(e.id), 'Event rejected')}>Reject</button>
            </div>
          </div>
        ))}</div>
      )}

      <h2>All events</h2>
      <div className="card table-wrap"><table className="table">
        <thead><tr><th>Title</th><th>Date</th><th>Status</th><th /></tr></thead>
        <tbody>{events.map((e) => (
          <tr key={e.id}><td>{e.title}</td><td>{formatDate(e.starts_at)}</td><td><span className={`status status-${e.status.toLowerCase()}`}>{e.status.toLowerCase()}</span></td>
            <td className="row-actions">{e.status !== 'APPROVED' && <button className="btn btn-ghost btn-sm" onClick={() => act(() => adminApi.approve(e.id), 'Approved')}>Approve</button>}{e.status === 'APPROVED' && <button className="btn btn-ghost btn-sm" onClick={() => act(() => adminApi.reject(e.id), 'Unpublished')}>Unpublish</button>}</td></tr>
        ))}</tbody></table></div>

      <h2>Users</h2>
      <input className="search-input" placeholder="Search users by name or email" value={q} onChange={(e) => setQ(e.target.value)} aria-label="Search users" />
      <div className="card table-wrap"><table className="table">
        <thead><tr><th>Name</th><th>Email</th><th>Role</th><th>Active</th></tr></thead>
        <tbody>{users.map((u) => (
          <tr key={u.id}><td>{u.name}</td><td>{u.email}</td>
            <td><select value={u.role} disabled={u.id === me.id} onChange={(e) => act(() => adminApi.updateUser(u.id, { role: e.target.value }), 'Role updated')} aria-label={`Role of ${u.name}`}>{['ATTENDEE', 'ORGANISER', 'ADMIN'].map((r) => <option key={r}>{r}</option>)}</select></td>
            <td><input type="checkbox" checked={u.is_active} disabled={u.id === me.id} onChange={(e) => act(() => adminApi.updateUser(u.id, { is_active: e.target.checked }), e.target.checked ? 'User enabled' : 'User disabled')} aria-label={`Active: ${u.name}`} /></td></tr>
        ))}</tbody></table></div>
    </div>
  )
}
