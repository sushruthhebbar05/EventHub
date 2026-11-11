import { Route, Routes } from 'react-router-dom'
import MainLayout from './layouts/MainLayout'
import ProtectedRoute from './components/ProtectedRoute'
import Landing from './pages/Landing'
import Login from './pages/Login'
import Register from './pages/Register'
import Events from './pages/Events'
import EventDetails from './pages/EventDetails'
import SeatSelection from './pages/SeatSelection'
import Checkout from './pages/Checkout'
import Payment from './pages/Payment'
import BookingSuccess from './pages/BookingSuccess'
import MyTickets from './pages/MyTickets'
import Profile from './pages/Profile'
import OrganiserDashboard from './pages/OrganiserDashboard'
import CreateEvent from './pages/CreateEvent'
import ManageEvents from './pages/ManageEvents'
import CheckIn from './pages/CheckIn'
import AdminDashboard from './pages/AdminDashboard'
import NotFound from './pages/NotFound'

const ORG = ['ORGANISER', 'ADMIN']
const guard = (el, roles) => <ProtectedRoute roles={roles}>{el}</ProtectedRoute>

export default function App() {
  return (
    <Routes>
      <Route element={<MainLayout />}>
        <Route index element={<Landing />} />
        <Route path="login" element={<Login />} />
        <Route path="register" element={<Register />} />
        <Route path="events" element={<Events />} />
        <Route path="events/:id" element={<EventDetails />} />
        <Route path="events/:id/seats" element={guard(<SeatSelection />)} />
        <Route path="checkout/:bookingId" element={guard(<Checkout />)} />
        <Route path="payment/:bookingId" element={guard(<Payment />)} />
        <Route path="booking-success/:bookingId" element={guard(<BookingSuccess />)} />
        <Route path="tickets" element={guard(<MyTickets />)} />
        <Route path="profile" element={guard(<Profile />)} />
        <Route path="organiser" element={guard(<OrganiserDashboard />, ORG)} />
        <Route path="organiser/events" element={guard(<ManageEvents />, ORG)} />
        <Route path="organiser/events/new" element={guard(<CreateEvent />, ORG)} />
        <Route path="organiser/events/:id/edit" element={guard(<CreateEvent />, ORG)} />
        <Route path="organiser/check-in" element={guard(<CheckIn />, ORG)} />
        <Route path="admin" element={guard(<AdminDashboard />, ['ADMIN'])} />
        <Route path="*" element={<NotFound />} />
      </Route>
    </Routes>
  )
}
