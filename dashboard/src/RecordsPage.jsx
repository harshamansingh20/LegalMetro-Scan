import { useEffect, useState } from 'react'
import { Search } from 'lucide-react'
import { api } from './api.js'
import { Kicker, Meter, STATUS, Tag, shortWhen } from './ui.jsx'

const PAGE = 25
const scoreStatus = (st) => (st === 'compliant' ? 'pass' : st === 'needs_review' ? 'review' : 'fail')

export default function RecordsPage() {
  const [f, setF] = useState({ q: '', status: '', reviewed: '', date_from: '', date_to: '' })
  const [page, setPage] = useState(0)
  const [data, setData] = useState(null)
  const [err, setErr] = useState('')

  useEffect(() => {
    const params = new URLSearchParams(Object.entries(f).filter(([, v]) => v))
    params.set('limit', PAGE)
    params.set('offset', page * PAGE)
    const t = setTimeout(() => api(`/scans?${params}`).then(setData, (e) => setErr(e.message)), 250) // debounce typing
    return () => clearTimeout(t)
  }, [f, page])

  const set = (k) => (e) => { setPage(0); setF({ ...f, [k]: e.target.value }) }
  const open = (id) => (location.hash = `#/scans/${id}`)

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Scanned records</h1>
          <p>Every scan is kept permanently. Records and officer reviews are append-only — nothing here can be edited or deleted.</p>
        </div>
        {data && <div className="count-big"><div className="readout">{data.total}</div><Kicker>{Object.values(f).some(Boolean) ? 'Matching records' : 'Records on file'}</Kicker></div>}
      </div>
      <div className="page-body">
        <section className="card">
          <div className="filters">
            <label className="field">Search
              <span className="search"><Search size={17} /><input className="input" type="search" placeholder="Product, label text, barcode, submitter…" value={f.q} onChange={set('q')} /></span>
            </label>
            <label className="field">Outcome
              <select className="input" value={f.status} onChange={set('status')}>
                <option value="">Any outcome</option>
                <option value="non_compliant">Likely non-compliant</option>
                <option value="needs_review">Needs review</option>
                <option value="compliant">Compliant</option>
              </select>
            </label>
            <label className="field">Officer review
              <select className="input" value={f.reviewed} onChange={set('reviewed')}>
                <option value="">Reviewed or not</option>
                <option value="false">Awaiting review</option>
                <option value="true">Officer reviewed</option>
              </select>
            </label>
            <label className="field">From<input className="input" type="date" value={f.date_from} onChange={set('date_from')} /></label>
            <label className="field">To<input className="input" type="date" value={f.date_to} onChange={set('date_to')} /></label>
          </div>
          {err && <p className="error" style={{ padding: '0 20px' }}>{err}</p>}
          {data && (
            <>
              <div className="table-wrap">
                <table className="data records">
                  <thead>
                    <tr><th>No.</th><th>Scanned</th><th>Commodity</th><th>Manufacturer / packer</th><th>Barcode</th><th>Submitted by</th><th>Score</th><th>Outcome</th></tr>
                  </thead>
                  <tbody>
                    {data.items.map((s) => (
                      <tr key={s.id} className="link" tabIndex={0} onClick={() => open(s.id)} onKeyDown={(e) => e.key === 'Enter' && open(s.id)}>
                        <td className="id" data-label="No.">{s.id}</td>
                        <td className="when" data-label="Scanned">{shortWhen(s.created_at)}</td>
                        <td className="strong" data-label="Commodity">{s.commodity || <span className="muted">—</span>}</td>
                        <td className="clip" data-label="Manufacturer" title={s.manufacturer || ''}>{s.manufacturer || <span className="muted">not found</span>}</td>
                        <td className="code" data-label="Barcode">{s.barcode || <span style={{ color: 'var(--tick)' }}>—</span>}</td>
                        <td data-label="Submitted by">{s.user.name}</td>
                        <td data-label="Score">{s.score != null ? <Meter v={s.score / 100} status={scoreStatus(s.status)} threshold={false} width={64} /> : '—'}</td>
                        <td data-label="Outcome">
                          <Tag s={s.status}>{STATUS[s.status]}</Tag>
                          {s.reviewed && <div className="sub">Officer reviewed</div>}
                        </td>
                      </tr>
                    ))}
                    {!data.items.length && <tr><td colSpan={8} className="empty" style={{ textAlign: 'center' }}>No scans match these filters.</td></tr>}
                  </tbody>
                </table>
              </div>
              <div className="pager">
                <span>Showing {data.items.length ? page * PAGE + 1 : 0}–{page * PAGE + data.items.length} of {data.total}</span>
                <button className="btn quiet" disabled={!page} onClick={() => setPage(page - 1)}>← Previous</button>
                <button className="btn" disabled={(page + 1) * PAGE >= data.total} onClick={() => setPage(page + 1)}>Next →</button>
              </div>
            </>
          )}
        </section>
      </div>
    </>
  )
}
