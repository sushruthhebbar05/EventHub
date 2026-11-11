import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Briefcase, Laugh, Mic2, Music, PartyPopper, Search, Trophy, Drama } from 'lucide-react'
import { eventsApi } from '../services/endpoints'
import EventCard from '../components/EventCard'
import HeroSeats from '../components/HeroSeats'
import { ErrorBox, Spinner } from '../components/Feedback'

const CATEGORIES = [
  ['Concert', Music], ['Conference', Briefcase], ['Comedy', Laugh], ['Sports', Trophy],
  ['Theatre', Drama], ['Festival', PartyPopper], ['Workshop', Mic2],
]

function Row({ title, subtitle, to, events }) {
  if (!events.length) return null
  return (
    <section className="section container">
      <div className="section-head">
        <div><h2>{title}</h2>{subtitle && <p className="muted">{subtitle}</p>}</div>
        <Link to={to} className="btn btn-ghost btn-sm">See all</Link>
      </div>
      <div className="grid grid-events">{events.map((e) => <EventCard key={e.id} event={e} />)}</div>
    </section>
  )
}

export default function Landing() {
  const navigate = useNavigate()
  const [q, setQ] = useState('')
  const [city, setCity] = useState('')
  const [data, setData] = useState(null)
  const [cities, setCities] = useState([])
  const [error, setError] = useState('')

  useEffect(() => {
    Promise.all([
      eventsApi.list({ sort: 'popular', page_size: 3 }),
      eventsApi.list({ page_size: 8 }),
      eventsApi.list({ category: 'Concert', sort: 'popular', page_size: 3 }),
      eventsApi.list({ category: 'Conference', page_size: 3 }),
      eventsApi.filters(),
    ]).then(([featured, upcoming, concerts, conferences, filters]) => {
      setData({ featured: featured.items, upcoming: upcoming.items, concerts: concerts.items, conferences: conferences.items })
      setCities(filters.cities)
    }).catch(() => setError('Could not load events. Is the backend running on port 8000?'))
  }, [])

  const submit = (e) => {
    e.preventDefault()
    const p = new URLSearchParams()
    if (q.trim()) p.set('q', q.trim())
    if (city) p.set('city', city)
    navigate(`/events?${p.toString()}`)
  }

  return (
    <>
      <section className="hero">
        <div className="container hero-grid">
          <div>
            <h1 className="hero-title">The seat you tap is the seat you get.</h1>
            <p className="hero-sub">Browse concerts, conferences and live shows. Choose exact seats on a live map, hold them for five minutes, and pay without racing anyone.</p>
            <form className="search-bar" onSubmit={submit} role="search">
              <Search size={18} className="muted" />
              <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search events by name" aria-label="Search events" />
              <select value={city} onChange={(e) => setCity(e.target.value)} aria-label="City">
                <option value="">All cities</option>
                {cities.map((c) => <option key={c}>{c}</option>)}
              </select>
              <button className="btn btn-primary" type="submit">Search</button>
            </form>
          </div>
          <HeroSeats />
        </div>
      </section>

      <section className="section container">
        <h2>Popular categories</h2>
        <div className="chips">
          {CATEGORIES.map(([name, Icon]) => (
            <Link key={name} to={`/events?category=${name}`} className="chip"><Icon size={18} /> {name}</Link>
          ))}
        </div>
      </section>

      {error && <div className="container"><ErrorBox message={error} /></div>}
      {!data && !error && <div className="page-center"><Spinner size={32} /></div>}
      {data && (
        <>
          <Row title="Featured events" subtitle="Filling up fastest right now" to="/events?sort=popular" events={data.featured} />
          <Row title="Upcoming events" to="/events" events={data.upcoming} />
          <Row title="Trending concerts" to="/events?category=Concert" events={data.concerts} />
          <Row title="Conferences" subtitle="Learn from people who ship" to="/events?category=Conference" events={data.conferences} />
        </>
      )}
    </>
  )
}
