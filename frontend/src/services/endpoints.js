import { api } from './api'

const data = (p) => p.then((r) => r.data)

export const authApi = {
  register: (body) => data(api.post('/auth/register', body)),
  login: (body) => data(api.post('/auth/login', body)),
  me: () => data(api.get('/auth/me')),
  updateProfile: (body) => data(api.patch('/users/me', body)),
}

export const eventsApi = {
  list: (params) => data(api.get('/events', { params })),
  filters: () => data(api.get('/events/filters')),
  get: (id) => data(api.get(`/events/${id}`)),
  create: (body) => data(api.post('/events', body)),
  update: (id, body) => data(api.put(`/events/${id}`, body)),
  remove: (id) => api.delete(`/events/${id}`),
  seats: (id) => data(api.get(`/events/${id}/seats`)),
  uploadImage: (file) => {
    const form = new FormData()
    form.append('file', file)
    return data(api.post('/events/upload-image', form))
  },
}

export const venuesApi = { list: () => data(api.get('/venues')) }

export const holdsApi = {
  create: (event_id, seat_ids) => data(api.post('/holds', { event_id, seat_ids })),
  mine: (event_id) => data(api.get('/holds/mine', { params: { event_id } })),
  release: (id) => api.delete(`/holds/${id}`),
}

export const bookingsApi = {
  create: (hold_ids, key) => data(api.post('/bookings', { hold_ids }, { headers: { 'Idempotency-Key': key } })),
  list: () => data(api.get('/bookings')),
  get: (id) => data(api.get(`/bookings/${id}`)),
  cancel: (id) => data(api.post(`/bookings/${id}/cancel`)),
}

export const paymentsApi = {
  pay: (body, key) => data(api.post('/payments', body, { headers: { 'Idempotency-Key': key } })),
}

export const ticketsApi = {
  qr: (id) => api.get(`/tickets/${id}/qr`, { responseType: 'blob' }).then((r) => r.data),
  download: (id) => api.get(`/tickets/${id}/download`, { responseType: 'blob' }).then((r) => r.data),
  checkIn: (code) => data(api.post('/tickets/check-in', { code })),
}

export const organiserApi = {
  summary: () => data(api.get('/organiser/summary')),
  events: () => data(api.get('/organiser/events')),
  stats: () => data(api.get('/organiser/events/stats')),
  bookings: (id) => data(api.get(`/organiser/events/${id}/bookings`)),
}

export const adminApi = {
  stats: () => data(api.get('/admin/stats')),
  users: (q) => data(api.get('/admin/users', { params: { q } })),
  updateUser: (id, body) => data(api.patch(`/admin/users/${id}`, body)),
  events: (status) => data(api.get('/admin/events', { params: { status } })),
  approve: (id) => data(api.post(`/admin/events/${id}/approve`)),
  reject: (id) => data(api.post(`/admin/events/${id}/reject`)),
}
