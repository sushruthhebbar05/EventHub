import { useEffect, useRef, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { Lock } from 'lucide-react'
import { bookingsApi, paymentsApi } from '../services/endpoints'
import { errorMessage } from '../services/api'
import { formatINR, newKey } from '../services/format'
import { useToast } from '../context/ToastContext'
import CountdownBadge from '../components/CountdownBadge'
import { ErrorBox, PageLoader, Spinner } from '../components/Feedback'

export default function Payment() {
  const { bookingId } = useParams()
  const navigate = useNavigate()
  const toast = useToast()
  const [booking, setBooking] = useState(null)
  const [error, setError] = useState('')
  const [formError, setFormError] = useState('')
  const [busy, setBusy] = useState(false)
  const [card, setCard] = useState({ card_number: '4242 4242 4242 4242', card_holder: '', expiry: '12/30', cvv: '123' })
  // One idempotency key per payment *attempt*. Double-clicks reuse it, so the card can never be charged twice.
  const key = useRef(newKey())

  useEffect(() => {
    bookingsApi.get(bookingId).then((b) => {
      if (b.status === 'CONFIRMED') navigate(`/booking-success/${b.id}`, { replace: true })
      else setBooking(b)
    }).catch((e) => setError(errorMessage(e)))
  }, [bookingId, navigate])

  const set = (k) => (e) => setCard({ ...card, [k]: e.target.value })
  const formatCard = (v) => v.replace(/\D/g, '').slice(0, 19).replace(/(.{4})/g, '$1 ').trim()

  const submit = async (e) => {
    e.preventDefault()
    if (busy) return
    setBusy(true)
    setFormError('')
    try {
      await paymentsApi.pay({ booking_id: Number(bookingId), ...card }, key.current)
      toast.success('Payment successful!')
      navigate(`/booking-success/${bookingId}`, { replace: true })
    } catch (err) {
      const status = err.response?.status
      if (status === 410) {
        toast.error('Your hold expired before payment. Please pick your seats again.')
        navigate(`/events/${booking.event.id}/seats`, { replace: true })
        return
      }
      setFormError(errorMessage(err, 'Payment failed'))
      if (status === 402) key.current = newKey() // a declined attempt is final; a retry is a new attempt
    } finally {
      setBusy(false)
    }
  }

  if (error) return <div className="container page"><ErrorBox message={error} /></div>
  if (!booking) return <PageLoader />
  if (booking.status !== 'PENDING_PAYMENT') {
    return <div className="container page narrow"><div className="alert alert-error">This booking can no longer be paid ({booking.status.toLowerCase().replace('_', ' ')}). <Link to={`/events/${booking.event.id}`}>Back to event</Link></div></div>
  }

  return (
    <div className="container page narrow">
      <h1>Payment</h1>
      <CountdownBadge expiresAt={booking.expires_at} onExpire={() => navigate(`/events/${booking.event.id}/seats`)} />
      <form className="card pay-card" onSubmit={submit}>
        <div className="pay-total"><span className="muted">Amount to pay</span><strong>{formatINR(booking.total_amount)}</strong></div>
        {formError && <div className="alert alert-error" role="alert">{formError}</div>}
        <label className="field">Card number<input inputMode="numeric" required value={card.card_number} onChange={(e) => setCard({ ...card, card_number: formatCard(e.target.value) })} autoComplete="cc-number" /></label>
        <label className="field">Name on card<input required minLength={2} value={card.card_holder} onChange={set('card_holder')} autoComplete="cc-name" /></label>
        <div className="row-2">
          <label className="field">Expiry (MM/YY)<input required placeholder="12/30" value={card.expiry} onChange={set('expiry')} autoComplete="cc-exp" /></label>
          <label className="field">CVV<input required inputMode="numeric" maxLength={4} value={card.cvv} onChange={set('cvv')} autoComplete="cc-csc" /></label>
        </div>
        <button className="btn btn-primary btn-block" disabled={busy}>{busy ? <><Spinner size={16} /> Processing…</> : <><Lock size={16} /> Pay {formatINR(booking.total_amount)}</>}</button>
        <p className="small muted center">Mock gateway: no real money moves. Use <code>4242 4242 4242 4242</code> to succeed or <code>4000 0000 0000 0002</code> to see a decline.</p>
      </form>
    </div>
  )
}
