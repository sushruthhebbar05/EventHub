import { formatINR } from '../services/format'

const LEGEND = [
  ['available', 'Available'],
  ['selected', 'Selected'],
  ['held', 'Held by others'],
  ['booked', 'Booked'],
]

/**
 * Visual seat map. `viewStatus(seat)` returns one of: available | selected | held | booked.
 * Colours: green / blue / orange / grey. Selected also shows a tick and booked a cross, so colour is not the only signal.
 */
export default function SeatMap({ sections, viewStatus, onSeatClick, busy = new Set(), disabled = false }) {
  return (
    <div className="seatmap">
      <div className="legend">
        {LEGEND.map(([k, label]) => (
          <span key={k} className="legend-item"><i className={`seat seat-${k} seat-static`} /> {label}</span>
        ))}
      </div>
      <div className="seatmap-scroll">
        <div className="seatmap-inner">
          <div className="stage" aria-hidden="true"><span>STAGE</span></div>
          {sections.map((section) => (
            <section key={section.name} className="seat-section" aria-label={`${section.name} section`}>
              <div className="seat-section-head">
                <strong>{section.name}</strong>
                <span className="muted">{formatINR(section.price)} per seat</span>
              </div>
              {section.rows.map((row) => (
                <div key={row.label} className="seat-row">
                  <span className="row-label">{row.label}</span>
                  <div className="seat-row-seats">
                    {row.seats.map((seat) => {
                      const state = viewStatus(seat)
                      const unavailable = state === 'booked' || state === 'held'
                      return (
                        <button
                          key={seat.id}
                          type="button"
                          className={`seat seat-${state} ${busy.has(seat.id) ? 'seat-busy' : ''}`}
                          disabled={disabled || unavailable || busy.has(seat.id)}
                          aria-pressed={state === 'selected'}
                          aria-label={`${section.name} row ${row.label} seat ${seat.number}, ${formatINR(section.price)}, ${state}`}
                          title={`${row.label}${seat.number} · ${formatINR(section.price)} · ${state}`}
                          onClick={() => onSeatClick(seat, section, row)}
                        >
                          {seat.number}
                        </button>
                      )
                    })}
                  </div>
                  <span className="row-label">{row.label}</span>
                </div>
              ))}
            </section>
          ))}
        </div>
      </div>
    </div>
  )
}
