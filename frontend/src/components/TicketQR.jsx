import { useEffect, useState } from 'react'
import { Download } from 'lucide-react'
import { ticketsApi } from '../services/endpoints'
import { downloadBlob } from '../services/format'
import { useToast } from '../context/ToastContext'
import { Spinner } from './Feedback'

/** Fetches the QR PNG with the auth header (an <img src> can't send one) and shows it as an object URL. */
export function QRImage({ ticketId, size = 160 }) {
  const [src, setSrc] = useState(null)
  useEffect(() => {
    let url
    let alive = true
    ticketsApi.qr(ticketId).then((blob) => {
      if (!alive) return
      url = URL.createObjectURL(blob)
      setSrc(url)
    }).catch(() => {})
    return () => { alive = false; if (url) URL.revokeObjectURL(url) }
  }, [ticketId])
  return (
    <div className="qr-box" style={{ width: size, height: size }}>
      {src ? <img src={src} alt="Ticket QR code" width={size} height={size} /> : <Spinner />}
    </div>
  )
}

export function DownloadTicketButton({ ticketId, small = true }) {
  const toast = useToast()
  const [busy, setBusy] = useState(false)
  const run = async () => {
    setBusy(true)
    try {
      downloadBlob(await ticketsApi.download(ticketId), `eventhub-ticket-${ticketId}.png`)
    } catch {
      toast.error('Could not download the ticket')
    } finally {
      setBusy(false)
    }
  }
  return (
    <button className={`btn btn-outline ${small ? 'btn-sm' : ''}`} onClick={run} disabled={busy}>
      <Download size={16} /> {busy ? 'Preparing…' : 'Download'}
    </button>
  )
}
