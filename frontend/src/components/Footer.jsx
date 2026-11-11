import { Link } from 'react-router-dom'
import { Logo } from './Navbar'

export default function Footer() {
  return (
    <footer className="footer">
      <div className="container footer-grid">
        <div>
          <Logo />
          <p className="muted footer-blurb">Find an event, pick your exact seat and watch availability update live. A seat is never sold twice.</p>
        </div>
        <div>
          <h4>Explore</h4>
          <Link to="/events">All events</Link>
          <Link to="/events?category=Concert">Concerts</Link>
          <Link to="/events?category=Conference">Conferences</Link>
          <Link to="/events?category=Comedy">Comedy</Link>
        </div>
        <div>
          <h4>Account</h4>
          <Link to="/tickets">My tickets</Link>
          <Link to="/profile">Profile</Link>
          <Link to="/register">Become an organiser</Link>
        </div>
      </div>
      <div className="container footer-bottom muted">© {new Date().getFullYear()} EventHub. Demo project - payments are simulated.</div>
    </footer>
  )
}
