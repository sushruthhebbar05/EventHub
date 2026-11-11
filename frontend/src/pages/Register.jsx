import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { errorMessage } from '../services/api'
import { Spinner } from '../components/Feedback'

export default function Register() {
  const { register } = useAuth()
  const navigate = useNavigate()
  const [form, setForm] = useState({ name: '', email: '', password: '', role: 'ATTENDEE' })
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value })

  const submit = async (e) => {
    e.preventDefault()
    setBusy(true)
    setError('')
    try {
      const user = await register(form)
      navigate(user.role === 'ORGANISER' ? '/organiser' : '/events', { replace: true })
    } catch (err) {
      setError(errorMessage(err, 'Could not create the account'))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="container auth-wrap">
      <form className="card auth-card" onSubmit={submit}>
        <h1>Create your account</h1>
        {error && <div className="alert alert-error" role="alert">{error}</div>}
        <label className="field">Full name<input required minLength={2} value={form.name} onChange={set('name')} autoComplete="name" /></label>
        <label className="field">Email<input type="email" required value={form.email} onChange={set('email')} autoComplete="email" /></label>
        <label className="field">Password
          <input type="password" required minLength={8} value={form.password} onChange={set('password')} autoComplete="new-password" />
          <span className="small muted">At least 8 characters, with a letter and a number.</span>
        </label>
        <fieldset className="role-pick">
          <legend className="small muted">I want to</legend>
          <label className={form.role === 'ATTENDEE' ? 'active' : ''}><input type="radio" name="role" checked={form.role === 'ATTENDEE'} onChange={() => setForm({ ...form, role: 'ATTENDEE' })} /> Attend events</label>
          <label className={form.role === 'ORGANISER' ? 'active' : ''}><input type="radio" name="role" checked={form.role === 'ORGANISER'} onChange={() => setForm({ ...form, role: 'ORGANISER' })} /> Organise events</label>
        </fieldset>
        <button className="btn btn-primary btn-block" disabled={busy}>{busy ? <Spinner size={16} /> : 'Create account'}</button>
        <p className="muted center">Already registered? <Link to="/login">Log in</Link></p>
      </form>
    </div>
  )
}
