import { Navigate, useLocation } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { PageLoader } from './Feedback'

/** Hides pages from logged-out users and wrong roles. (The BACKEND enforces the same rules on every API call.) */
export default function ProtectedRoute({ roles, children }) {
  const { user, loading } = useAuth()
  const location = useLocation()
  if (loading) return <PageLoader />
  if (!user) return <Navigate to="/login" replace state={{ from: location.pathname + location.search }} />
  if (roles && !roles.includes(user.role)) {
    return (
      <div className="container page-center">
        <h1>Access denied</h1>
        <p className="muted">Your account ({user.role.toLowerCase()}) cannot open this page.</p>
      </div>
    )
  }
  return children
}
