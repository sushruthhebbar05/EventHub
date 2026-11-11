import { createContext, useCallback, useContext, useMemo, useState } from 'react'
import { CheckCircle2, Info, XCircle } from 'lucide-react'

const ToastContext = createContext(null)
const ICONS = { success: CheckCircle2, error: XCircle, info: Info }

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([])

  const push = useCallback((type, message) => {
    const id = Math.random().toString(36).slice(2)
    setToasts((t) => [...t.slice(-3), { id, type, message }])
    setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), 4500)
  }, [])

  const toast = useMemo(
    () => ({
      success: (m) => push('success', m),
      error: (m) => push('error', m),
      info: (m) => push('info', m),
    }),
    [push],
  )

  return (
    <ToastContext.Provider value={toast}>
      {children}
      <div className="toasts" role="status" aria-live="polite">
        {toasts.map((t) => {
          const Icon = ICONS[t.type]
          return (
            <div key={t.id} className={`toast toast-${t.type}`}>
              <Icon size={18} />
              <span>{t.message}</span>
            </div>
          )
        })}
      </div>
    </ToastContext.Provider>
  )
}

export const useToast = () => useContext(ToastContext)
