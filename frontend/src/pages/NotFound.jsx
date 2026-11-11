import { Link } from 'react-router-dom'

export default function NotFound() {
  return (
    <div className="container page-center">
      <div className="nf-code">404</div>
      <h1>That page isn't on the program</h1>
      <p className="muted">The link may be broken, or the page may have moved.</p>
      <Link to="/" className="btn btn-primary">Back to home</Link>
    </div>
  )
}
