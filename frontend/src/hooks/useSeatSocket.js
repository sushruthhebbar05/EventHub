import { useEffect, useRef, useState } from 'react'

/**
 * Live seat updates for one event over WebSocket.
 *  - onUpdate(seats)  receives [{seat_id, status}] whenever any user holds / releases / books a seat
 *  - onResync()       is called after every (re)connect so the page can refetch and never miss a change
 * Reconnects automatically with exponential back-off if the connection drops.
 */
export function useSeatSocket(eventId, onUpdate, onResync) {
  const [connected, setConnected] = useState(false)
  const handlers = useRef({ onUpdate, onResync })
  handlers.current = { onUpdate, onResync }

  useEffect(() => {
    if (!eventId) return undefined
    let ws
    let retry = 0
    let closed = false
    let pingTimer
    let reconnectTimer

    const connect = () => {
      const proto = window.location.protocol === 'https:' ? 'wss' : 'ws'
      ws = new WebSocket(`${proto}://${window.location.host}/ws/events/${eventId}`)
      ws.onopen = () => {
        retry = 0
        setConnected(true)
        handlers.current.onResync?.()
        pingTimer = setInterval(() => ws.readyState === WebSocket.OPEN && ws.send('ping'), 25000)
      }
      ws.onmessage = (e) => {
        try {
          const msg = JSON.parse(e.data)
          if (msg.type === 'seat_update') handlers.current.onUpdate?.(msg.seats)
        } catch {
          /* "pong" and anything else non-JSON is ignored */
        }
      }
      ws.onclose = () => {
        setConnected(false)
        clearInterval(pingTimer)
        if (!closed) {
          reconnectTimer = setTimeout(connect, Math.min(10000, 500 * 2 ** retry++))
        }
      }
      ws.onerror = () => ws.close()
    }

    connect()
    return () => {
      closed = true
      clearInterval(pingTimer)
      clearTimeout(reconnectTimer)
      ws?.close()
    }
  }, [eventId])

  return connected
}
