import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import { TOKEN_KEY } from '../services/api'
import { authApi } from '../services/endpoints'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(!!localStorage.getItem(TOKEN_KEY))

  const logout = useCallback(() => {
    localStorage.removeItem(TOKEN_KEY)
    setUser(null)
  }, [])

  // Restore the session on page load.
  useEffect(() => {
    if (!localStorage.getItem(TOKEN_KEY)) return
    authApi.me().then(setUser).catch(logout).finally(() => setLoading(false))
  }, [logout])

  // The axios interceptor fires this when the server says the token is no longer valid.
  useEffect(() => {
    window.addEventListener('eventhub:logout', logout)
    return () => window.removeEventListener('eventhub:logout', logout)
  }, [logout])

  const startSession = (res) => {
    localStorage.setItem(TOKEN_KEY, res.access_token)
    setUser(res.user)
    return res.user
  }

  const value = useMemo(
    () => ({
      user,
      loading,
      isOrganiser: user?.role === 'ORGANISER' || user?.role === 'ADMIN',
      isAdmin: user?.role === 'ADMIN',
      login: async (email, password) => startSession(await authApi.login({ email, password })),
      register: async (body) => startSession(await authApi.register(body)),
      updateUser: setUser,
      logout,
    }),
    [user, loading, logout],
  )
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export const useAuth = () => useContext(AuthContext)
