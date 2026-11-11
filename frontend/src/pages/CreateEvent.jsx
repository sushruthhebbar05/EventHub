import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { Plus, Trash2 } from 'lucide-react'
import { eventsApi, venuesApi } from '../services/endpoints'
import { errorMessage } from '../services/api'
import { formatINR } from '../services/format'
import { useToast } from '../context/ToastContext'
import { PageLoader, Spinner } from '../components/Feedback'

const CATEGORIES = ['Concert', 'Conference', 'Comedy', 'Sports', 'Theatre', 'Festival', 'Workshop']
const toLocalInput = (iso) => { const d = new Date(iso); d.setMinutes(d.getMinutes() - d.getTimezoneOffset()); return d.toISOString().slice(0, 16) }

export default function CreateEvent() {
  const { id } = useParams() // present when editing
  const editing = !!id
  const navigate = useNavigate()
  const toast = useToast()
  const [venues, setVenues] = useState([])
  const [loading, setLoading] = useState(editing)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [venueMode, setVenueMode] = useState('existing')
  const [f, setF] = useState({ title: '', description: '', category: 'Concert', image_url: '', starts_at: '', venue_id: '' })
  const [venue, setVenue] = useState({ name: '', city: '', address: '', capacity: 500 })
  const [sections, setSections] = useState([{ name: 'General', rows: 5, seats_per_row: 10, price: 500 }])
  const [prices, setPrices] = useState({}) // edit mode: section name -> price

  useEffect(() => { venuesApi.list().then(setVenues).catch(() => {}) }, [])
  useEffect(() => {
    if (!editing) return
    eventsApi.get(id).then((e) => {
      setF({ title: e.title, description: e.description, category: e.category, image_url: e.image_url || '', starts_at: toLocalInput(e.starts_at), venue_id: e.venue.id })
      setSections(e.sections)
      setPrices(Object.fromEntries(e.sections.map((s) => [s.name, Number(s.price)])))
    }).catch((err) => setError(errorMessage(err))).finally(() => setLoading(false))
  }, [editing, id])

  const set = (k) => (e) => setF({ ...f, [k]: e.target.value })
  const setSec = (i, k, v) => setSections(sections.map((s, j) => (j === i ? { ...s, [k]: v } : s)))
  const totalSeats = sections.reduce((n, s) => n + Number(s.rows) * Number(s.seats_per_row), 0)

  const upload = async (file) => {
    if (!file) return
    try { setF({ ...f, image_url: (await eventsApi.uploadImage(file)).url }); toast.success('Image uploaded') } catch (e) { toast.error(errorMessage(e)) }
  }

  const submit = async (e) => {
    e.preventDefault()
    setBusy(true)
    setError('')
    try {
      const common = { title: f.title, description: f.description, category: f.category, image_url: f.image_url || null, starts_at: new Date(f.starts_at).toISOString() }
      if (editing) {
        await eventsApi.update(id, { ...common, section_prices: prices })
        toast.success('Event updated')
      } else {
        const body = {
          ...common,
          sections: sections.map((s) => ({ name: s.name, rows: Number(s.rows), seats_per_row: Number(s.seats_per_row), price: String(s.price) })),
          ...(venueMode === 'existing' ? { venue_id: Number(f.venue_id) } : { venue: { ...venue, capacity: Number(venue.capacity) } }),
        }
        const created = await eventsApi.create(body)
        toast.success(created.status === 'PENDING' ? 'Event created - it will go live once an admin approves it' : 'Event created and live!')
      }
      navigate('/organiser/events')
    } catch (err) {
      setError(errorMessage(err))
    } finally { setBusy(false) }
  }

  if (loading) return <PageLoader />
  return (
    <div className="container page narrow">
      <h1>{editing ? 'Edit event' : 'Create event'}</h1>
      <form className="card form-card" onSubmit={submit}>
        {error && <div className="alert alert-error" role="alert">{error}</div>}
        <label className="field">Title<input required minLength={3} value={f.title} onChange={set('title')} /></label>
        <label className="field">Description<textarea rows={4} value={f.description} onChange={set('description')} /></label>
        <div className="row-2">
          <label className="field">Category<select value={f.category} onChange={set('category')}>{CATEGORIES.map((c) => <option key={c}>{c}</option>)}</select></label>
          <label className="field">Start date &amp; time<input type="datetime-local" required value={f.starts_at} onChange={set('starts_at')} /></label>
        </div>
        <div className="field">Poster image
          <div className="row-2">
            <input placeholder="Image URL (optional)" value={f.image_url} onChange={set('image_url')} aria-label="Image URL" />
            <input type="file" accept="image/png,image/jpeg,image/webp" onChange={(e) => upload(e.target.files[0])} aria-label="Upload image" />
          </div>
          {f.image_url && <img className="preview" src={f.image_url} alt="Poster preview" />}
        </div>

        {!editing && (
          <>
            <h3>Venue</h3>
            <div className="tabs">
              <button type="button" className={venueMode === 'existing' ? 'tab active' : 'tab'} onClick={() => setVenueMode('existing')}>Choose existing</button>
              <button type="button" className={venueMode === 'new' ? 'tab active' : 'tab'} onClick={() => setVenueMode('new')}>Add new venue</button>
            </div>
            {venueMode === 'existing' ? (
              <label className="field">Venue<select required value={f.venue_id} onChange={set('venue_id')}><option value="">Select a venue…</option>{venues.map((v) => <option key={v.id} value={v.id}>{v.name} - {v.city}</option>)}</select></label>
            ) : (
              <div className="row-2">
                <label className="field">Venue name<input required value={venue.name} onChange={(e) => setVenue({ ...venue, name: e.target.value })} /></label>
                <label className="field">City<input required value={venue.city} onChange={(e) => setVenue({ ...venue, city: e.target.value })} /></label>
                <label className="field">Address<input required value={venue.address} onChange={(e) => setVenue({ ...venue, address: e.target.value })} /></label>
                <label className="field">Capacity<input type="number" min={1} required value={venue.capacity} onChange={(e) => setVenue({ ...venue, capacity: e.target.value })} /></label>
              </div>
            )}
          </>
        )}

        <h3>Seating &amp; pricing</h3>
        {editing ? (
          <>
            <p className="muted small">The seat layout is fixed once created. You can change prices of seats that are not yet booked.</p>
            {sections.map((s) => (
              <label key={s.name} className="field">{s.name} price (₹)<input type="number" min={0} value={prices[s.name]} onChange={(e) => setPrices({ ...prices, [s.name]: Number(e.target.value) })} /></label>
            ))}
          </>
        ) : (
          <>
            {sections.map((s, i) => (
              <div key={i} className="section-editor">
                <label className="field">Section name<input required value={s.name} onChange={(e) => setSec(i, 'name', e.target.value)} /></label>
                <label className="field">Rows (max 26)<input type="number" min={1} max={26} required value={s.rows} onChange={(e) => setSec(i, 'rows', e.target.value)} /></label>
                <label className="field">Seats / row<input type="number" min={1} max={40} required value={s.seats_per_row} onChange={(e) => setSec(i, 'seats_per_row', e.target.value)} /></label>
                <label className="field">Price (₹)<input type="number" min={0} required value={s.price} onChange={(e) => setSec(i, 'price', e.target.value)} /></label>
                <button type="button" className="icon-btn" disabled={sections.length === 1} onClick={() => setSections(sections.filter((_, j) => j !== i))} aria-label="Remove section"><Trash2 size={18} /></button>
              </div>
            ))}
            <div className="actions left">
              <button type="button" className="btn btn-outline btn-sm" disabled={sections.length >= 10} onClick={() => setSections([...sections, { name: '', rows: 5, seats_per_row: 10, price: 500 }])}><Plus size={16} /> Add section</button>
              <span className="muted small">{totalSeats} seats in total{sections[0] ? ` · cheapest ${formatINR(Math.min(...sections.map((s) => Number(s.price))))}` : ''}</span>
            </div>
          </>
        )}
        <button className="btn btn-primary" disabled={busy}>{busy ? <Spinner size={16} /> : editing ? 'Save changes' : 'Create event'}</button>
      </form>
    </div>
  )
}
