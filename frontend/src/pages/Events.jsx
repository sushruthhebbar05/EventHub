import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { Search } from 'lucide-react'
import { eventsApi } from '../services/endpoints'
import EventCard from '../components/EventCard'
import Pagination from '../components/Pagination'
import { Empty, ErrorBox, Spinner } from '../components/Feedback'

export default function Events() {
  const [params, setParams] = useSearchParams()
  const [filters, setFilters] = useState({ cities: [], categories: [] })
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)
  const [q, setQ] = useState(params.get('q') || '')

  const get = (k) => params.get(k) || ''
  const update = (patch) => {
    const next = new URLSearchParams(params)
    Object.entries({ page: '1', ...patch }).forEach(([k, v]) => (v ? next.set(k, v) : next.delete(k)))
    setParams(next, { replace: true })
  }

  useEffect(() => { eventsApi.filters().then(setFilters).catch(() => {}) }, [])

  // debounce the search box so we don't call the API on every keystroke
  useEffect(() => {
    const t = setTimeout(() => { if (q !== get('q')) update({ q }) }, 350)
    return () => clearTimeout(t)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [q])

  const query = params.toString()
  useEffect(() => {
    setLoading(true)
    setError('')
    const date = params.get('date')
    eventsApi.list({
      q: params.get('q') || undefined, city: params.get('city') || undefined, category: params.get('category') || undefined,
      date_from: date || undefined, date_to: date || undefined, sort: params.get('sort') || 'date',
      page: Number(params.get('page') || 1), page_size: 9,
    }).then(setResult).catch(() => setError('Could not load events.')).finally(() => setLoading(false))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [query])

  const clear = () => { setQ(''); setParams({}, { replace: true }) }

  return (
    <div className="container page">
      <h1>Find your next event</h1>
      <div className="filters card">
        <label className="field grow"><span className="sr-only">Search</span>
          <div className="input-icon"><Search size={16} /><input placeholder="Search by event name" value={q} onChange={(e) => setQ(e.target.value)} /></div>
        </label>
        <label className="field">City
          <select value={get('city')} onChange={(e) => update({ city: e.target.value })}>
            <option value="">All cities</option>{filters.cities.map((c) => <option key={c}>{c}</option>)}
          </select>
        </label>
        <label className="field">Category
          <select value={get('category')} onChange={(e) => update({ category: e.target.value })}>
            <option value="">All categories</option>{filters.categories.map((c) => <option key={c}>{c}</option>)}
          </select>
        </label>
        <label className="field">Date<input type="date" value={get('date')} onChange={(e) => update({ date: e.target.value })} /></label>
        <label className="field">Sort
          <select value={get('sort') || 'date'} onChange={(e) => update({ sort: e.target.value })}>
            <option value="date">Soonest first</option><option value="popular">Most popular</option>
          </select>
        </label>
        <button className="btn btn-ghost" onClick={clear}>Clear</button>
      </div>

      {error && <ErrorBox message={error} />}
      {loading && !result && <div className="page-center"><Spinner size={32} /></div>}
      {result && (
        <>
          <p className="muted results-count">{result.total} event{result.total === 1 ? '' : 's'} found {loading && <Spinner size={14} />}</p>
          {result.items.length === 0 ? (
            <Empty title="No events match your filters">Try another city, category or date.</Empty>
          ) : (
            <div className="grid grid-events">{result.items.map((e) => <EventCard key={e.id} event={e} />)}</div>
          )}
          <Pagination page={result.page} pages={result.pages} onChange={(p) => { update({ page: String(p) }); window.scrollTo(0, 0) }} />
        </>
      )}
    </div>
  )
}
