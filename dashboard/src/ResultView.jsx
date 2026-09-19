import { useEffect, useState } from 'react'
import { AlertTriangle, CircleCheck, ClipboardCheck, Download, Eye, EyeOff, Pencil } from 'lucide-react'
import { api, download } from './api.js'
import { Corners, Gauge, Kicker, Meter, STATUS, Tag, VERDICT, rupees, when } from './ui.jsx'
import { money } from './money.js'

function useAuthedImage(path) {
  const [url, setUrl] = useState(null)
  useEffect(() => {
    if (!path) return setUrl(null)
    let u
    api(path, { raw: true }).then((b) => setUrl((u = URL.createObjectURL(b))), () => setUrl(null))
    return () => u && URL.revokeObjectURL(u)
  }, [path])
  return url
}

export default function ResultView({ scan, user, onUpdate, back }) {
  const eff = scan.effective
  const fields = Object.fromEntries(eff.fields.map((f) => [f.id, f]))
  const [hover, setHover] = useState(null)
  const [editing, setEditing] = useState(false)
  const [err, setErr] = useState('')
  const reg = eff.barcode?.registry
  const passed = eff.counts?.pass ?? eff.fields.filter((f) => f.status === 'pass').length
  const officer = user.role === 'officer'

  return (
    <article>
      <div className="crumbs">
        {back ? <a href={back[0]}>← {back[1]}</a> : <span className="kicker ink">Result</span>}
        <span className="sep">/</span>
        <Kicker>Record #{scan.id} · {when(scan.created_at)}</Kicker>
      </div>

      <section className="verdict" aria-live="polite">
        <div>
          <Tag s={eff.status}>{eff.reviewed ? 'Verdict · officer reviewed' : 'Verdict · needs officer confirmation'}</Tag>
          <h1 className={eff.status}>{VERDICT[eff.status]}</h1>
          <div className="product">
            {reg ? `${reg.brand} — ` : ''}{fields.commodity_name?.value || 'Commodity name not detected'}
            {fields.net_quantity?.value && <span className="muted num" style={{ fontSize: 14 }}> · {fields.net_quantity.value}</span>}
          </div>
          <div className="meta">
            {scan.ocr.elapsed_ms > 0 && <span>OCR {(scan.ocr.elapsed_ms / 1000).toFixed(1)} s</span>}
            <span>Ruleset {eff.rules_version}</span>
            <span>By {scan.user.name}</span>
            <span>{eff.reviewed ? 'Officer reviewed' : 'Not yet reviewed'}</span>
          </div>
        </div>
        <div className="gauge">
          <Kicker>Compliance score</Kicker>
          <Gauge value={(eff.score ?? 0) / 100} status={eff.status} />
          <div className="readout">{eff.score ?? 0}<span style={{ fontSize: 18, color: 'var(--ink-3)' }}>%</span></div>
          <div className="small muted">{passed} of {eff.fields.length} declarations pass</div>
        </div>
        <div className="penalty">
          <Kicker>S.36(1) · indicative max. fine</Kicker>
          <div className="readout">{eff.penalty?.pending_review ? '—' : rupees(eff.penalty?.amount, 0)}</div>
          <p>
            {eff.penalty?.amount ? 'First-offence ceiling if the violations are confirmed. The competent authority decides the actual penalty.'
              : eff.penalty?.pending_review ? 'Pending the officer’s review of the flagged declarations.'
              : 'No exposure on the declarations checked.'}
          </p>
          <div className="buttons">
            {officer && <button className="btn primary" onClick={() => { setEditing(true); document.getElementById(`audit-${scan.id}`)?.scrollIntoView({ behavior: 'smooth' }) }}><Pencil size={16} /> Review</button>}
            <button className="btn" onClick={() => download(`/scans/${scan.id}/report.pdf`, `legalmetro-scan-${scan.id}.pdf`).catch((e) => setErr(e.message))}><Download size={16} /> PDF</button>
          </div>
          {err && <span className="error small">{err}</span>}
        </div>
      </section>

      <div className="result-grid">
        <div className="stack">
          {scan.has_image ? <Evidence scan={scan} hover={hover} /> : <ListingCard scan={scan} />}
          <BarcodeCard scan={scan} fields={fields} />
          <Declarations scan={scan} fields={fields} />
        </div>
        <div className="stack">
          <Audit scan={scan} officer={officer} setHover={setHover} onUpdate={onUpdate} editing={editing} setEditing={setEditing} />
          <History scan={scan} officer={officer} />
        </div>
      </div>
    </article>
  )
}

function Evidence({ scan, hover }) {
  const img = useAuthedImage(`/scans/${scan.id}/image`)
  const [boxes, setBoxes] = useState(true)
  const { width: w, height: h } = scan.ocr
  const bc = scan.effective.barcode
  const n = Math.max(12, Math.round((w || 1000) / 55)) // number-badge size scales with the photo
  return (
    <section className="card">
      <div className="card-head">
        <h2>Evidence · label photo</h2>
        <div className="right">
          <button className="toggle" onClick={() => setBoxes(!boxes)} aria-pressed={boxes}>{boxes ? <Eye size={14} /> : <EyeOff size={14} />} Detections</button>
          {w && <span className="kicker">{w} × {h}</span>}
        </div>
      </div>
      <div className="evidence">
        {img && w ? (
          <div className="frame corners-brass">
            <svg viewBox={`0 0 ${w} ${h}`} role="img" aria-label="Label photo with detected declarations outlined and numbered">
              <image href={img} width={w} height={h} />
              {boxes && scan.effective.fields.map((f, i) => f.box && (
                <g key={f.id}>
                  <rect x={f.box[0] - 5} y={f.box[1] - 5} width={f.box[2] - f.box[0] + 10} height={f.box[3] - f.box[1] + 10}
                        className={`ev-box ${f.status} ${hover === f.id ? 'hot' : ''}`}><title>{f.label}: {STATUS[f.status]}</title></rect>
                  <rect x={f.box[2] + 5} y={f.box[1] - 5} width={n * 2} height={n * 1.5} fill={`var(--${f.status}-mark)`} />
                  <text x={f.box[2] + 5 + n} y={f.box[1] - 5 + n * 1.1} textAnchor="middle" fill="#fff" fontSize={n} fontWeight="700">{String(i + 1).padStart(2, '0')}</text>
                </g>
              ))}
              {boxes && bc?.box && bc.source === 'label' && (
                <rect x={bc.box[0] - 5} y={bc.box[1] - 5} width={bc.box[2] - bc.box[0] + 10} height={bc.box[3] - bc.box[1] + 10} className="ev-box barcode"><title>Barcode {bc.code}</title></rect>
              )}
            </svg>
            <Corners />
          </div>
        ) : <p style={{ color: 'var(--tick)', margin: 0, padding: 24 }}>Loading photo…</p>}
      </div>
      <div className="ev-legend">
        <span><i style={{ borderColor: 'var(--pass-mark)' }} />Compliant</span>
        <span><i style={{ borderColor: 'var(--review-mark)' }} />Review</span>
        <span><i style={{ borderColor: 'var(--fail-mark)' }} />Violation</span>
        <span><i style={{ borderColor: 'var(--brass)', borderStyle: 'dashed' }} />Barcode</span>
        <span className="note">Numbers match the audit →</span>
      </div>
    </section>
  )
}

// Legacy: a few records came from the removed e-commerce audit (pasted listing text, no photo).
function ListingCard({ scan }) {
  const l = scan.listing || {}
  return (
    <section className="card">
      <div className="card-head"><h2>Listing text (legacy e-commerce record)</h2></div>
      <div className="card-body">
        {l.url && <p style={{ marginTop: 0, overflowWrap: 'anywhere' }}><Kicker>Listing URL (recorded, not fetched)</Kicker>{l.url}</p>}
        <div className="raw-lines" style={{ padding: 0 }}>{scan.ocr.lines.map((line, i) => <div key={i}><span>{line.text}</span></div>)}</div>
      </div>
    </section>
  )
}

function BarcodeCard({ scan, fields }) {
  const bc = scan.effective.barcode
  const photo = useAuthedImage(scan.has_barcode_image ? `/scans/${scan.id}/barcode-image` : null)
  if (!bc && scan.source === 'ecommerce') return null
  const labelMrp = money(fields.mrp?.value)
  return (
    <section className="card">
      <div className="card-head">
        <h2>Barcode verification</h2>
        {bc && <div className="right"><Tag s={bc.mismatches.length ? 'review' : bc.registry ? 'pass' : 'missing'}>{bc.mismatches.length ? 'Mismatch' : bc.registry ? 'Matched' : 'Not in registry'}</Tag></div>}
      </div>
      {!bc ? (
        <p className="empty">No barcode found{scan.has_barcode_image ? ' on the label or in the barcode photo' : ' on the label'}. Add a close-up of the barcode to cross-check MRP and net quantity.</p>
      ) : (
        <div className="card-body stack" style={{ gap: 14 }}>
          <div className="barcode-top">
            {photo && <img className="barcode-thumb" src={photo} alt="Uploaded barcode close-up" />}
            <div>
              <div className="barcode-code">{bc.code}</div>
              <div className="facts">
                <span className="fact">{bc.type.replace('_', '-')}</span>
                <span className={`fact ${bc.valid_checksum ? 'good' : 'bad'}`}>{bc.valid_checksum ? <CircleCheck size={12} /> : <AlertTriangle size={12} />}Check digit {bc.valid_checksum ? 'valid' : 'invalid'}</span>
                {bc.gs1_org && <span className="fact" title="The GS1 prefix shows which GS1 member issued the number, not where the product was made">GS1 {bc.gs1_org}</span>}
                <span className="fact">From {bc.source === 'barcode_photo' ? 'barcode photo' : 'label photo'}</span>
              </div>
            </div>
          </div>
          {bc.registry ? (
            <div className="registry">
              <div className="registry-head kicker">Product registry record (demo data)</div>
              <dl className="registry-grid">
                <dt>Product</dt><dd>{bc.registry.brand} {bc.registry.name}</dd>
                <dt>Net quantity</dt><dd>{bc.registry.net_quantity}</dd>
                <dt>Registered MRP</dt><dd>{rupees(bc.registry.mrp)}</dd>
                {labelMrp != null && <><dt>Label MRP</dt><dd className={Math.abs(labelMrp - bc.registry.mrp) > 0.01 ? 'bad' : ''}>{rupees(labelMrp)}</dd></>}
                <dt>Manufacturer</dt><dd>{bc.registry.manufacturer}</dd>
              </dl>
            </div>
          ) : <p className="small muted" style={{ margin: 0 }}>This GTIN isn’t in the product registry, so MRP and net quantity can’t be cross-checked.</p>}
          {bc.mismatches.map((m) => <div key={m} className="alert"><AlertTriangle size={17} />{m}</div>)}
        </div>
      )}
    </section>
  )
}

function Declarations({ scan, fields }) {
  const v = (id) => fields[id]?.value
  const reg = scan.effective.barcode?.registry
  const rows = [
    ['Brand & commodity', [reg?.brand, v('commodity_name')].filter(Boolean).join(' — ')],
    ['Net quantity', v('net_quantity')],
    ['MRP', v('mrp')],
    ['Unit sale price', v('unit_sale_price')],
    ['Mfg / packing date', v('packing_date')],
    ['Manufacturer / packer', v('manufacturer')],
    ['Consumer care', v('consumer_care')],
    ['Barcode (GTIN)', scan.effective.barcode?.code],
  ]
  return (
    <section className="card">
      <div className="card-head"><h2>Extracted declarations</h2></div>
      <dl className="kv">
        {rows.map(([k, val]) => <div key={k}><dt>{k}</dt><dd className={val ? 'num' : 'none'}>{val || 'Not found'}</dd></div>)}
      </dl>
    </section>
  )
}

function Audit({ scan, officer, setHover, onUpdate, editing, setEditing }) {
  const eff = scan.effective
  const machine = Object.fromEntries(scan.machine_result.fields.map((f) => [f.id, f]))
  const [draft, setDraft] = useState({})
  const [note, setNote] = useState('')
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')
  const c = eff.counts || {}

  const set = (id, k, val) => setDraft((d) => ({ ...d, [id]: { status: eff.fields.find((f) => f.id === id).status, ...d[id], [k]: val } }))
  const changed = Object.keys(draft).length

  const save = async () => {
    setBusy(true)
    setErr('')
    try {
      onUpdate(await api(`/scans/${scan.id}/reviews`, { json: { overrides: draft, note } }))
      setDraft({})
      setNote('')
      setEditing(false)
    } catch (e) {
      setErr(e.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className="card" id={`audit-${scan.id}`} style={{ scrollMarginTop: 16 }}>
      <div className="card-head">
        <h2>Rule-by-rule audit</h2>
        <div className="right counts">
          <span className="pass">{c.pass ?? 0} pass</span><span className="sep">·</span>
          <span className="fail">{(c.fail ?? 0) + (c.missing ?? 0)} violations</span><span className="sep">·</span>
          <span className="review">{c.review ?? 0} review</span>
        </div>
      </div>
      <div>
        {eff.fields.map((f, i) => {
          const msgs = f.messages.length ? f.messages : [f.pass_message || 'Declaration present.']
          const d = draft[f.id]
          return (
            <div key={f.id} className={`rule-row ${f.status === 'fail' || f.status === 'missing' ? 'flagged' : ''} ${d ? 'hot' : ''}`}
                 onMouseEnter={() => setHover(f.id)} onMouseLeave={() => setHover(null)}>
              <div className={`rule-num ${f.status}`}>{String(i + 1).padStart(2, '0')}</div>
              <div>
                <div className="rule-title">{f.label}</div>
                <div className="rule-cite">{f.rule_ref} · Packaged Commodities Rules, 2011</div>
                {msgs.map((m) => <p key={m} className={`rule-msg ${f.status === 'pass' ? '' : f.status}`}>{m}</p>)}
                <div className="rule-foot">
                  {f.value && <span className="value-chip">{f.value}</span>}
                  {f.confidence > 0 && <Meter v={f.confidence} />}
                </div>
              </div>
              <div><Tag s={f.status} /></div>
              {f.reviewed && (
                <div className="reviewed-note">
                  Officer <b>{f.reviewed.by}</b> changed {STATUS[machine[f.id].status]} → {STATUS[f.status]}
                  {f.reviewed.note && <> — “{f.reviewed.note}”</>}
                </div>
              )}
              {editing && (
                <div className="override">
                  <select className="input" aria-label={`Officer decision for ${f.label}`} value={d?.status || f.status} onChange={(e) => set(f.id, 'status', e.target.value)}>
                    <option value="pass">Compliant</option>
                    <option value="review">Needs review</option>
                    <option value="fail">Violation</option>
                    <option value="missing">Missing</option>
                  </select>
                  <input className="input" aria-label={`Corrected value for ${f.label}`} placeholder="Corrected value (optional)" value={d?.value || ''} onChange={(e) => set(f.id, 'value', e.target.value)} />
                  <input className="input" aria-label={`Note for ${f.label}`} placeholder="Note (optional)" value={d?.note || ''} onChange={(e) => set(f.id, 'note', e.target.value)} />
                </div>
              )}
            </div>
          )
        })}
      </div>
      {officer && (
        <div className="review-bar">
          {!editing ? (
            <>
              <span className="hint">Confirm or override the machine result. Saved as a new review — the scan itself is never edited.</span>
              <button className="btn primary" onClick={() => setEditing(true)}><Pencil size={16} /> Officer review</button>
            </>
          ) : (
            <>
              <input className="input" aria-label="Overall review note" placeholder="Overall review note" value={note} onChange={(e) => setNote(e.target.value)} />
              <button className="btn quiet" onClick={() => { setEditing(false); setDraft({}) }}>Cancel</button>
              <button className="btn primary" disabled={busy || !changed} onClick={save}>
                <ClipboardCheck size={16} /> {busy ? 'Saving…' : `Save review${changed ? ` (${changed})` : ''}`}
              </button>
              {err && <span className="error small">{err}</span>}
            </>
          )}
        </div>
      )}
    </section>
  )
}

function History({ scan, officer }) {
  const time = (iso) => new Date(iso).toLocaleString('en-IN', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false })
  return (
    <>
      <div className="two">
        <section className="card">
          <div className="card-head"><h2>Officer reviews</h2></div>
          {scan.reviews.length ? (
            <ol className="trail">
              {scan.reviews.map((r) => (
                <li key={r.id}>
                  <span>{time(r.created_at)}</span>
                  <span>
                    <b>{r.reviewer}</b> → <Tag s={r.status} />
                    <div className="small muted" style={{ marginTop: 4 }}>{Object.entries(r.overrides).map(([k, o]) => `${k.replace(/_/g, ' ')}: ${STATUS[o.status]}${o.value ? ` (“${o.value}”)` : ''}`).join(' · ')}</div>
                    {r.note && <div className="small">“{r.note}”</div>}
                  </span>
                </li>
              ))}
            </ol>
          ) : <p className="empty">No officer review yet. Reviews are added as new records — the machine result above is never edited.</p>}
        </section>
        {officer && scan.audit && (
          <section className="card">
            <div className="card-head"><h2>Audit trail · append-only</h2></div>
            <ol className="trail">
              {scan.audit.map((a, i) => <li key={i}><span>{time(a.created_at)}</span><span><b style={{ fontWeight: 500 }}>{a.action.replace(/_/g, ' ')}</b> · {a.actor || 'system'}</span></li>)}
            </ol>
          </section>
        )}
      </div>
      {scan.has_image && (
        <details className="card raw">
          <summary>Raw OCR text — {scan.ocr.lines.length} lines (PaddleOCR)</summary>
          <div className="raw-lines">{scan.ocr.lines.map((l, i) => <div key={i}><span>{l.text}</span><span className="muted num">{Math.round(l.confidence * 100)}%</span></div>)}</div>
        </details>
      )}
    </>
  )
}
