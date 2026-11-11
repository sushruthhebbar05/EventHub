import { useState } from 'react'
import { ScanLine } from 'lucide-react'
import { ticketsApi } from '../services/endpoints'
import { errorMessage } from '../services/api'
import { seatLabel } from '../services/format'

export default function CheckIn() {
  const [code, setCode] = useState('')
  const [result, setResult] = useState(null)

  const submit = async (e) => {
    e.preventDefault()
    try {
      const r = await ticketsApi.checkIn(code.trim())
      setResult({ ok: true, text: r.message, ticket: r.ticket })
    } catch (err) {
      setResult({ ok: false, text: errorMessage(err, 'Invalid ticket') })
    }
    setCode('')
  }

  return (
    <div className="container page narrow">
      <h1>Entry check-in</h1>
      <p className="muted">Type or paste the ticket code (the text inside the QR code). A ticket can be admitted only once.</p>
      <form className="card form-card" onSubmit={submit}>
        <label className="field">Ticket code<input required autoFocus value={code} onChange={(e) => setCode(e.target.value)} /></label>
        <button className="btn btn-primary"><ScanLine size={16} /> Validate ticket</button>
      </form>
      {result && (
        <div className={`alert ${result.ok ? 'alert-success' : 'alert-error'}`} role="status">
          <div><strong>{result.text}</strong>{result.ticket && <div>{result.ticket.event.title} · {seatLabel(result.ticket)}</div>}</div>
        </div>
      )}
    </div>
  )
}
