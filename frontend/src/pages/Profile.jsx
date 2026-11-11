import { useState } from 'react'
import { useAuth } from '../context/AuthContext'
import { authApi } from '../services/endpoints'
import { errorMessage } from '../services/api'
import { useToast } from '../context/ToastContext'

export default function Profile() {
  const { user, updateUser } = useAuth()
  const toast = useToast()
  const [name, setName] = useState(user.name)
  const [pw, setPw] = useState({ current_password: '', new_password: '' })

  const save = async (body, done) => {
    try {
      updateUser(await authApi.updateProfile(body))
      toast.success(done)
      return true
    } catch (e) {
      toast.error(errorMessage(e))
      return false
    }
  }

  return (
    <div className="container page narrow">
      <h1>My profile</h1>
      <div className="card form-card">
        <div className="profile-id">
          <div className="avatar">{user.name[0]}</div>
          <div><strong>{user.email}</strong><br /><span className="badge">{user.role}</span></div>
        </div>
        <form onSubmit={(e) => { e.preventDefault(); save({ name }, 'Name updated') }}>
          <label className="field">Full name<input value={name} minLength={2} required onChange={(e) => setName(e.target.value)} /></label>
          <button className="btn btn-primary" disabled={name === user.name}>Save name</button>
        </form>
      </div>
      <div className="card form-card">
        <h3>Change password</h3>
        <form onSubmit={async (e) => { e.preventDefault(); if (await save(pw, 'Password changed')) setPw({ current_password: '', new_password: '' }) }}>
          <label className="field">Current password<input type="password" required value={pw.current_password} onChange={(e) => setPw({ ...pw, current_password: e.target.value })} autoComplete="current-password" /></label>
          <label className="field">New password<input type="password" required minLength={8} value={pw.new_password} onChange={(e) => setPw({ ...pw, new_password: e.target.value })} autoComplete="new-password" /></label>
          <button className="btn btn-primary">Update password</button>
        </form>
      </div>
    </div>
  )
}
