import { useState } from 'react'
import { Link, NavLink, useNavigate } from 'react-router-dom'
import { LogOut, Menu, Ticket, User, X } from 'lucide-react'
import { useAuth } from '../context/AuthContext'

export function Logo() {
  return (
    <Link to="/" className="logo" aria-label="EventHub home">
      <span className="logo-mark"><Ticket size={18} /></span>
      <span className="logo-text">EventHub</span>
    </Link>
  )
}

export default function Navbar() {
  const { user, isOrganiser, isAdmin, logout } = useAuth()
  const [open, setOpen] = useState(false)
  const navigate = useNavigate()
  const close = () => setOpen(false)

  const links = [
    ['/events', 'Events'],
    ...(user ? [['/tickets', 'My Tickets']] : []),
    ...(isOrganiser ? [['/organiser', 'Organiser']] : []),
    ...(isAdmin ? [['/admin', 'Admin']] : []),
  ]

  return (
    <header className="navbar">
      <div className="container navbar-inner">
        <Logo />
        <nav className={`nav-links ${open ? 'open' : ''}`}>
          {links.map(([to, label]) => (
            <NavLink key={to} to={to} end={to === '/organiser'} onClick={close}>{label}</NavLink>
          ))}
          <div className="nav-auth">
            {user ? (
              <>
                <Link to="/profile" className="btn btn-ghost btn-sm" onClick={close}><User size={16} /> {user.name.split(' ')[0]}</Link>
                <button className="btn btn-outline btn-sm" onClick={() => { logout(); close(); navigate('/') }}><LogOut size={16} /> Log out</button>
              </>
            ) : (
              <>
                <Link to="/login" className="btn btn-ghost btn-sm" onClick={close}>Log in</Link>
                <Link to="/register" className="btn btn-primary btn-sm" onClick={close}>Sign up</Link>
              </>
            )}
          </div>
        </nav>
        <button className="icon-btn nav-toggle" onClick={() => setOpen(!open)} aria-label="Toggle menu" aria-expanded={open}>
          {open ? <X size={22} /> : <Menu size={22} />}
        </button>
      </div>
    </header>
  )
}
