import { useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { errorMessage } from '../services/api'
import { Spinner } from '../components/Feedback'

export default function Login() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  const submit = async (e) => {
    e.preventDefault()
    setBusy(true)
    setError('')
    try {
      const user = await login(email, password)
      navigate(location.state?.from || (user.role === 'ATTENDEE' ? '/events' : '/organiser'), { replace: true })
    } catch (err) {
      setError(errorMessage(err, 'Login failed'))
    } finally {
      setBusy(false)
    }
  }

  const fill = (e, p) => { setEmail(e); setPassword(p) }

  return (
    <div className="container auth-wrap">
      <form className="card auth-card" onSubmit={submit}>
        <h1>Welcome back</h1>
        <p className="muted">Log in to book seats and see your tickets.</p>
        {error && <div className="alert alert-error" role="alert">{error}</div>}
        <label className="field">Email<input type="email" required value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="email" /></label>
        <label className="field">Password<input type="password" required value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="current-password" /></label>
        <button className="btn btn-primary btn-block" disabled={busy}>{busy ? <Spinner size={16} /> : 'Log in'}</button>
        <p className="muted center">New here? <Link to="/register">Create an account</Link></p>
        <div className="demo-box">
          <div className="small muted">Demo accounts (click to fill)</div>
          <button type="button" className="chip chip-sm" onClick={() => fill('attendee@eventhub.dev', 'Attendee@123')}>Attendee</button>
          <button type="button" className="chip chip-sm" onClick={() => fill('organiser@eventhub.dev', 'Organiser@123')}>Organiser</button>
          <button type="button" className="chip chip-sm" onClick={() => fill('admin@eventhub.dev', 'Admin@123')}>Admin</button>
        </div>
      </form>
    </div>
  )
}
