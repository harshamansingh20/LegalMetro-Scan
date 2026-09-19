import { useEffect, useState } from 'react'
import { api } from './api.js'
import { Kicker, MARK, Tag, useTip } from './ui.jsx'

const OUTCOMES = [['compliant', 'Compliant'], ['needs_review', 'Needs review'], ['non_compliant', 'Likely non-compliant']]
const FIELD_STATES = [['fail', 'Violation'], ['missing', 'Missing'], ['review', 'Needs review']]
const dayLabel = (d) => new Date(d).toLocaleDateString('en-IN', { day: 'numeric', month: 'short' })
const lakh = (n) => (n >= 100000 ? [`₹${(n / 100000).toLocaleString('en-IN', { maximumFractionDigits: 1 })}`, 'lakh'] : [`₹${n.toLocaleString('en-IN')}`, ''])

const Legend = ({ items }) => (
  <div className="legend">{items.map(([k, label]) => <span key={k}><i style={{ background: MARK[k] }} />{label}</span>)}</div>
)

const Kpi = ({ label, value, unit, note, tone }) => (
  <div className={`kpi ${tone || ''}`}>
    <Kicker>{label}</Kicker>
    <div className="value"><span className="readout">{value}</span>{unit && <span className="unit">{unit}</span>}</div>
    <div className="note">{note}</div>
    <div className="ticks" aria-hidden="true" />
  </div>
)

function niceMax(n) {
  const steps = [4, 10, 20, 40, 50, 100, 200, 400, 500, 1000] // halve to whole numbers for the midline
  return steps.find((s) => s >= n) || Math.ceil(n / 1000) * 1000
}

export default function StatsPage() {
  const [days, setDays] = useState(7)
  const [s, setS] = useState(null)
  const [err, setErr] = useState('')
  const [tip, bind] = useTip()
  useEffect(() => { api(`/stats?days=${days}`).then(setS, (e) => setErr(e.message)) }, [days])

  const head = (
    <div className="page-head">
      <div>
        <h1>Where labels fall short</h1>
        <p>Outcomes after officer review where one exists. Totals cover every scan; the daily chart covers the selected window.</p>
      </div>
      <div className="seg" role="group" aria-label="Time window">
        {[7, 30, 90].map((d) => <button key={d} className={days === d ? 'on' : ''} aria-pressed={days === d} onClick={() => setDays(d)}>{d} days</button>)}
      </div>
    </div>
  )
  if (err) return <>{head}<p className="error page-body">{err}</p></>
  if (!s) return <>{head}<p className="muted page-body">Loading statistics…</p></>

  const total = (d) => d.compliant + d.needs_review + d.non_compliant
  const max = niceMax(Math.max(1, ...s.daily.map(total)))
  const fmax = Math.max(1, ...s.by_field.map((f) => f.fail + f.missing + f.review))
  const pct = (n) => Math.round((100 * n) / (s.total || 1))
  const [penVal, penUnit] = lakh(s.penalty_exposure)

  return (
    <>
      {tip}
      {head}
      <div className="page-body stack">
        <div className="kpis">
          <Kpi label="Scans" value={s.total} unit="total" note={`${s.reviewed} with an officer review`} />
          <Kpi label="Compliance rate" value={s.compliance_rate} unit="%" note={`${s.by_status.compliant} fully compliant labels`} tone="pass" />
          <Kpi label="Likely non-compliant" value={s.by_status.non_compliant} unit="labels" note={`${s.awaiting_review} awaiting officer review`} tone="fail" />
          <Kpi label="Penalty exposure" value={penVal} unit={penUnit} note="Indicative S.36(1) first-offence ceiling" />
          <Kpi label="Barcodes verified" value={s.barcodes.scanned} unit="GTINs" note={`${s.barcodes.registry_mismatches} registry mismatch${s.barcodes.registry_mismatches === 1 ? '' : 'es'}`} />
        </div>

        <div className="chart-row">
          <section className="card">
            <div className="card-head"><h2>Scans per day, by outcome</h2><div className="right"><Legend items={OUTCOMES} /></div></div>
            <div className="cols-wrap">
              <div className="cols" role="img" aria-label="Stacked columns of scans per day by outcome; values in the table view">
                {[0.5, 1].map((f) => <div key={f} className="gridline" style={{ bottom: `${f * 100}%` }}><span>{Math.round(max * f)}</span></div>)}
                {s.daily.map((d) => (
                  <div key={d.date} className="col" style={{ height: `${(total(d) / max) * 100}%` }}
                       {...bind(<><b>{dayLabel(d.date)}</b>{total(d)} scans · {d.compliant} compliant · {d.needs_review} review · {d.non_compliant} non-compliant</>)}>
                    {OUTCOMES.map(([k]) => d[k] > 0 && <span key={k} style={{ flex: d[k], background: MARK[k] }} />)}
                  </div>
                ))}
              </div>
            </div>
            <div className="col-axis"><span>{dayLabel(s.daily[0].date)}</span><span>Today</span></div>
            <details style={{ padding: '0 20px 14px' }}>
              <summary className="kicker">Table view</summary>
              <div className="table-wrap"><table className="data">
                <thead><tr><th>Date</th><th className="right">Compliant</th><th className="right">Review</th><th className="right">Non-compliant</th></tr></thead>
                <tbody>{s.daily.filter(total).map((d) => (
                  <tr key={d.date}><td className="when">{dayLabel(d.date)}</td><td className="right num">{d.compliant}</td><td className="right num">{d.needs_review}</td><td className="right num">{d.non_compliant}</td></tr>
                ))}</tbody>
              </table></div>
            </details>
          </section>

          <section className="card">
            <div className="card-head"><h2>Outcome split</h2></div>
            <div className="card-body">
              <div className="split" role="img" aria-label="Share of scans by outcome">
                {OUTCOMES.map(([k, label]) => s.by_status[k] > 0 && (
                  <span key={k} style={{ flex: s.by_status[k], background: MARK[k] }} {...bind(<><b>{label}</b>{s.by_status[k]} scans ({pct(s.by_status[k])}%)</>)} />
                ))}
              </div>
              <div className="ticks" style={{ marginTop: 4 }} aria-hidden="true" />
              <div style={{ marginTop: 14 }}>
                {OUTCOMES.map(([k, label]) => (
                  <div key={k} className="split-row"><span><i style={{ background: MARK[k] }} />{label}</span><b>{s.by_status[k]}</b><em>{pct(s.by_status[k])}%</em></div>
                ))}
              </div>
            </div>
          </section>
        </div>

        <section className="card">
          <div className="card-head"><h2>Flags by mandatory declaration</h2><div className="right"><Legend items={FIELD_STATES} /></div></div>
          <div className="card-body" style={{ paddingTop: 6, paddingBottom: 8 }}>
            {s.by_field.map((f) => {
              const tot = f.fail + f.missing + f.review
              return (
                <div key={f.id} className="hbar-row">
                  <div className="lbl">{f.label}<span className="ref">{f.rule_ref}</span></div>
                  <div className="hbar" style={{ width: `${(tot / fmax) * 100}%` }}>
                    {FIELD_STATES.map(([k, label]) => f[k] > 0 && <span key={k} style={{ flex: f[k], background: MARK[k] }} {...bind(<><b>{f.label}</b>{f[k]} × {label}</>)} />)}
                  </div>
                  <div className="total">{tot}</div>
                </div>
              )
            })}
          </div>
        </section>

        <div className="two">
          <section className="card">
            <div className="card-head"><h2>Most-flagged manufacturers / packers</h2></div>
            {s.top_flagged.length ? s.top_flagged.map((m) => (
              <div key={m.name} className="list-row"><span>{m.name}</span><span className="n">{m.scans} scans</span><span className="flag">{m.non_compliant} flagged</span></div>
            )) : <p className="empty">Nothing flagged yet.</p>}
          </section>
          <section className="card">
            <div className="card-head"><h2>Recently flagged</h2></div>
            {s.recent_flagged.length ? s.recent_flagged.map((r) => (
              <a key={r.id} href={`#/scans/${r.id}`} className="list-row">
                <span className="num" style={{ fontWeight: 700 }}>#{r.id}</span>
                <span><b style={{ display: 'block' }}>{r.commodity || 'Unnamed product'}</b><span className="small muted">{r.issues.join(' · ')}</span></span>
                <Tag s="non_compliant">Flagged</Tag>
              </a>
            )) : <p className="empty">Nothing flagged yet.</p>}
          </section>
        </div>
        <p className="small muted" style={{ margin: 0 }}>Penalty figures are indicative maxima under {s.penalty_section}; they are not assessments.</p>
      </div>
    </>
  )
}
