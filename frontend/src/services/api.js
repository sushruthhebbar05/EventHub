import axios from 'axios'

export const TOKEN_KEY = 'eventhub_token'

// All calls go to /api (proxied to FastAPI in dev, to nginx->backend in Docker).
export const api = axios.create({ baseURL: '/api', timeout: 20000 })

api.interceptors.request.use((config) => {
  const token = localStorage.getItem(TOKEN_KEY)
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

// A 401 on a logged-in session means the token expired/was revoked: drop it and tell the app.
api.interceptors.response.use(
  (res) => res,
  (err) => {
    const url = err.config?.url || ''
    if (err.response?.status === 401 && localStorage.getItem(TOKEN_KEY) && !url.includes('/auth/login')) {
      localStorage.removeItem(TOKEN_KEY)
      window.dispatchEvent(new Event('eventhub:logout'))
    }
    return Promise.reject(err)
  },
)

export function errorMessage(err, fallback = 'Something went wrong. Please try again.') {
  const detail = err?.response?.data?.detail
  if (typeof detail === 'string') return detail
  if (!err?.response) return 'Cannot reach the server. Is the backend running?'
  return fallback
}
