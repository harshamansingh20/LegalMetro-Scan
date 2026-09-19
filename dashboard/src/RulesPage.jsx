import { useEffect, useState } from 'react'
import { api } from './api.js'
import { Kicker } from './ui.jsx'

const CHECK_TEXT = {
  regex: 'Must contain',
  not_regex: 'Must not contain',
  min_height_ratio: 'Text size (approx.)',
  unit_price_consistency: 'Cross-check',
}
const inr = (n) => `₹${Number(n).toLocaleString('en-IN')}`

export default function RulesPage() {
  const [r, setR] = useState(null)
  const [err, setErr] = useState('')
  useEffect(() => { api('/rules').then(setR, (e) => setErr(e.message)) }, [])

  return (
    <>
      <div className="page-head">
        <div>
          <h1>The ruleset</h1>
          <p>Every scan is checked against this live ruleset. It is data, not code: edit <b>backend/app/rules.json</b> and the next scan uses it.</p>
        </div>
        {r && <div className="count-big"><Kicker>Version</Kicker><div className="readout" style={{ fontSize: 28, marginTop: 6 }}>{r.version}</div></div>}
      </div>
      {err && <p className="error page-body">{err}</p>}
      {!r && !err && <p className="muted page-body">Loading ruleset…</p>}
      {r && (
        <div className="page-body stack">
          <div className="rules-top">
            <section className="card strong card-body schedule" style={{ padding: '28px 30px' }}>
              <Kicker>Schedule of penalties</Kicker>
              <h2>{r.penalties.section}</h2>
              <p style={{ margin: 0, color: 'var(--ink-2)' }}>{r.penalties.offence}</p>
              <div className="schedule-grid">
                <span>First offence</span><b>up to {inr(r.penalties.first_offence_max)}</b>
                <span>Second offence</span><b>up to {inr(r.penalties.second_offence_max)}</b>
                <span>Subsequent offence</span><b>{r.penalties.subsequent}</b>
              </div>
              <p className="small muted" style={{ margin: '14px 0 0', lineHeight: 1.55 }}>{r.penalties.note}</p>
            </section>
            <section className="card card-body stack" style={{ padding: '28px 30px', gap: 14 }}>
              <Kicker>How a declaration is judged</Kicker>
              <div className="status-key">
                <div className="pass"><b>Compliant</b>Found, well-formed, read with ≥ {Math.round(r.review_threshold * 100)}% confidence.</div>
                <div className="review"><b>Needs review</b>A soft check failed, or confidence is below {Math.round(r.review_threshold * 100)}%.</div>
                <div className="fail"><b>Violation</b>Found, but a hard check failed (e.g. no PIN code).</div>
                <div className="missing"><b>Missing</b>No trace of the declaration on the label.</div>
              </div>
              <p className="small muted" style={{ margin: 0, lineHeight: 1.55 }}>{r.clause_ref_note}</p>
            </section>
          </div>

          <section className="card rule-list">
            <div className="card-head"><h2>The {r.fields.length} mandatory declarations</h2></div>
            {r.fields.map((f, i) => (
              <article key={f.id} className="rule-line">
                <span className="readout big">{String(i + 1).padStart(2, '0')}</span>
                <div className="what">
                  <span className="ref">{f.rule_ref}</span>
                  <h3>{f.label}</h3>
                  <p>{f.description}</p>
                  <span className={`badge ${f.required === true ? '' : 'soft'}`}>{f.required === true ? 'Mandatory' : 'Where applicable'}</span>
                </div>
                <div className="how">
                  <div>
                    <Kicker>Located by</Kicker>
                    <div className="kw">{f.extract.keywords.slice(0, 9).map((k) => <span key={k}>{k}</span>)}</div>
                  </div>
                  {f.checks.length > 0 && (
                    <div>
                      <Kicker>Checks</Kicker>
                      <ul className="check-list">
                        {f.checks.map((c, j) => (
                          <li key={j}><b className={c.severity === 'fail' ? 'fail' : 'review'}>{CHECK_TEXT[c.type] || c.type} · {c.severity === 'fail' ? 'violation' : 'review'}</b> — {c.message}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                  {f.extract.value_pattern && (
                    <details>
                      <summary className="kicker">Value pattern</summary>
                      <pre className="pattern">{f.extract.value_pattern}</pre>
                    </details>
                  )}
                </div>
              </article>
            ))}
          </section>
        </div>
      )}
    </>
  )
}
