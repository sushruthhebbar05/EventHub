import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { Radio, WifiOff } from 'lucide-react'
import { bookingsApi, eventsApi, holdsApi } from '../services/endpoints'
import { errorMessage } from '../services/api'
import { formatDate, formatINR, formatTime, seatLabel } from '../services/format'
import { useSeatSocket } from '../hooks/useSeatSocket'
import { useToast } from '../context/ToastContext'
import SeatMap from '../components/SeatMap'
import CountdownBadge from '../components/CountdownBadge'
import { ErrorBox, PageLoader, Spinner } from '../components/Feedback'

export default function SeatSelection() {
  const { id } = useParams()
  const navigate = useNavigate()
  const toast = useToast()
  const [event, setEvent] = useState(null)
  const [map, setMap] = useState(null)
  const [holds, setHolds] = useState({}) // seat_id -> hold (my active holds)
  const [pending, setPending] = useState(null) // an unpaid checkout I already started for this event
  const [busy, setBusy] = useState(new Set())
  const [checkingOut, setCheckingOut] = useState(false)
  const [error, setError] = useState('')

  // ---- loading -----------------------------------------------------------------
  const loadAll = useCallback(async () => {
    try {
      const [ev, seatMap, mine, bookings] = await Promise.all([
        eventsApi.get(id), eventsApi.seats(id), holdsApi.mine(id), bookingsApi.list(),
      ])
      setEvent(ev)
      setMap(seatMap)
      setHolds(Object.fromEntries(mine.map((h) => [h.seat_id, h])))
      setPending(bookings.find((b) => b.status === 'PENDING_PAYMENT' && b.event.id === Number(id)) || null)
    } catch (e) {
      setError(errorMessage(e, 'Could not load the seat map.'))
    }
  }, [id])
  useEffect(() => { loadAll() }, [loadAll])

  // ---- live updates --------------------------------------------------------------
  const myIds = useRef(new Set())
  myIds.current = new Set(Object.keys(holds).map(Number))

  const applyUpdates = useCallback((updates) => {
    const byId = new Map(updates.map((u) => [u.seat_id, u.status]))
    setMap((m) => m && {
      ...m,
      sections: m.sections.map((sec) => ({
        ...sec,
        rows: sec.rows.map((row) => ({ ...row, seats: row.seats.map((s) => (byId.has(s.id) ? { ...s, status: byId.get(s.id) } : s)) })),
      })),
    })
    // if the server released / sold a seat I thought I held, drop it from my selection
    setHolds((h) => {
      const next = { ...h }
      updates.forEach((u) => { if (next[u.seat_id] && u.status !== 'HELD') delete next[u.seat_id] })
      return next
    })
  }, [])
  const connected = useSeatSocket(id, applyUpdates, loadAll)

  // ---- selecting seats (every click is a real API call) ----------------------------
  const setBusyFor = (seatId, on) => setBusy((b) => { const n = new Set(b); on ? n.add(seatId) : n.delete(seatId); return n })

  const onSeatClick = async (seat) => {
    setBusyFor(seat.id, true)
    try {
      const mine = holds[seat.id]
      if (mine) {
        await holdsApi.release(mine.id)
        setHolds((h) => { const n = { ...h }; delete n[seat.id]; return n })
      } else {
        const res = await holdsApi.create(Number(id), [seat.id])
        setHolds((h) => ({ ...h, ...Object.fromEntries(res.holds.map((x) => [x.seat_id, x])) }))
      }
    } catch (e) {
      toast.error(errorMessage(e, 'Could not update your selection'))
      if (e.response?.status === 409) loadAll()
    } finally {
      setBusyFor(seat.id, false)
    }
  }

  const viewStatus = (seat) => (holds[seat.id] ? 'selected' : seat.status.toLowerCase())

  const selected = useMemo(() => Object.values(holds).sort((a, b) => a.id - b.id), [holds])
  const total = selected.reduce((sum, h) => sum + Number(h.price), 0)
  const earliest = selected.length ? selected.map((h) => h.expires_at).sort()[0] : null

  const onExpire = () => {
    if (!selected.length) return
    toast.error('Your 5-minute hold ran out and the seats were released.')
    setHolds({})
    loadAll()
  }

  const checkout = async () => {
    setCheckingOut(true)
    try {
      const ids = selected.map((h) => h.id).sort((a, b) => a - b)
      // Same holds => same key => the server returns the same booking, even if this is clicked twice.
      const booking = await bookingsApi.create(ids, `checkout-${ids.join('-')}`)
      navigate(`/checkout/${booking.id}`)
    } catch (e) {
      toast.error(errorMessage(e, 'Could not start checkout'))
      if ([410, 409].includes(e.response?.status)) loadAll()
    } finally {
      setCheckingOut(false)
    }
  }

  if (error) return <div className="container page"><ErrorBox message={error} onRetry={() => { setError(''); loadAll() }} /></div>
  if (!event || !map) return <PageLoader />

  return (
    <div className="container page">
      <div className="page-head">
        <div>
          <Link to={`/events/${id}`} className="muted small">← Back to event</Link>
          <h1>{event.title}</h1>
          <p className="muted">{formatDate(event.starts_at)} · {formatTime(event.starts_at)} · {event.venue.name}, {event.venue.city}</p>
        </div>
        <span className={`live-pill ${connected ? 'on' : 'off'}`}>{connected ? <><Radio size={14} /> Live</> : <><WifiOff size={14} /> Reconnecting…</>}</span>
      </div>

      {pending && (
        <div className="alert alert-info">
          You have an unpaid checkout for this event. <Link to={`/checkout/${pending.id}`}><strong>Resume checkout</strong></Link>
        </div>
      )}

      <div className="seat-layout">
        <SeatMap sections={map.sections} viewStatus={viewStatus} onSeatClick={onSeatClick} busy={busy} disabled={event.status !== 'APPROVED'} />

        <aside className="card summary">
          <h3>Your selection</h3>
          {earliest && <CountdownBadge expiresAt={earliest} onExpire={onExpire} />}
          {selected.length === 0 ? (
            <p className="muted">Tap a green seat to hold it for 5 minutes. Other people see it update instantly.</p>
          ) : (
            <ul className="summary-list">
              {selected.map((h) => (
                <li key={h.id}><span>{seatLabel(h)}</span><strong>{formatINR(h.price)}</strong></li>
              ))}
            </ul>
          )}
          <div className="summary-total"><span>Total</span><strong>{formatINR(total)}</strong></div>
          <button className="btn btn-primary btn-block" disabled={!selected.length || checkingOut} onClick={checkout}>
            {checkingOut ? <Spinner size={16} /> : 'Confirm & go to checkout'}
          </button>
          <p className="small muted">Up to 6 seats per booking.</p>
        </aside>
      </div>
    </div>
  )
}
