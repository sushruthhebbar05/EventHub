import { AlertTriangle, Loader2 } from 'lucide-react'

export function Spinner({ size = 20 }) {
  return <Loader2 className="spin" size={size} aria-label="Loading" />
}

export function PageLoader() {
  return <div className="page-center"><Spinner size={32} /></div>
}

export function ErrorBox({ message, onRetry }) {
  return (
    <div className="alert alert-error" role="alert">
      <AlertTriangle size={18} />
      <span>{message}</span>
      {onRetry && <button className="btn btn-outline btn-sm" onClick={onRetry}>Retry</button>}
    </div>
  )
}

export function Empty({ title, children }) {
  return (
    <div className="empty">
      <h3>{title}</h3>
      <p className="muted">{children}</p>
    </div>
  )
}
