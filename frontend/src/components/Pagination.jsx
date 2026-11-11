import { ChevronLeft, ChevronRight } from 'lucide-react'

export default function Pagination({ page, pages, onChange }) {
  if (pages <= 1) return null
  return (
    <div className="pagination">
      <button className="btn btn-outline btn-sm" disabled={page <= 1} onClick={() => onChange(page - 1)}><ChevronLeft size={16} /> Prev</button>
      <span className="muted">Page {page} of {pages}</span>
      <button className="btn btn-outline btn-sm" disabled={page >= pages} onClick={() => onChange(page + 1)}>Next <ChevronRight size={16} /></button>
    </div>
  )
}
