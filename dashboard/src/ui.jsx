import { useState } from 'react'
import { CircleCheck, CircleHelp, CircleMinus, CircleX } from 'lucide-react'

export const STATUS = {
  compliant: 'Compliant',
  needs_review: 'Needs review',
  non_compliant: 'Likely non-compliant',
  pass: 'Compliant',
  fail: 'Violation',
  missing: 'Missing',
  review: 'Needs review',
}

// Overall verdict headline — deliberately "likely": an officer makes the final call.
export const VERDICT = {
  compliant: 'Fully compliant',
  needs_review: 'Needs officer review',
  non_compliant: 'Likely non‑compliant', // non-breaking hyphen: never splits as "non-" / "compliant"
}

export const StatusIcon = ({ s, size = 14 }) => {
  const Icon = { pass: CircleCheck, compliant: CircleCheck, review: CircleHelp, needs_review: CircleHelp, missing: CircleMinus }[s] || CircleX
  return <Icon size={size} strokeWidth={2} aria-hidden="true" />
}

export const Tag = ({ s, children }) => (
  <span className={`tag ${s}`}><StatusIcon s={s} size={13} />{children || STATUS[s] || s}</span>
)

export const Kicker = ({ children, ink }) => <div className={`kicker${ink ? ' ink' : ''}`}>{children}</div>

/** Calibration / crop marks on the four corners of a position:relative parent. */
export const Corners = () => (
  <>
    <span className="corner tl" aria-hidden="true" /><span className="corner tr" aria-hidden="true" />
    <span className="corner bl" aria-hidden="true" /><span className="corner br" aria-hidden="true" />
  </>
)

/** Horizontal meter with the 80% review threshold marked. */
export const Meter = ({ v, status, threshold = true, width = 72 }) => {
  const pct = Math.round((v ?? 0) * 100)
  const s = status || (v >= 0.8 ? 'pass' : v >= 0.5 ? 'missing' : 'fail')
  return (
    <span className="meter" title={threshold ? `Confidence ${pct}% (review below 80%)` : `${pct}%`}>
      <span className="track" style={{ width }}>
        <span className={`fill mark-${s}`} style={{ width: `${pct}%` }} />
        {threshold && <span className="threshold" />}
      </span>
      {pct}%
    </span>
  )
}

/** Semicircular dial for the compliance score. */
export function Gauge({ value, status }) {
  const R = 86, CX = 110, CY = 104, len = Math.PI * R
  const v = Math.max(0, Math.min(1, value))
  const ticks = Array.from({ length: 11 }, (_, k) => {
    const a = Math.PI * (1 - k / 10), r1 = R + 10, r2 = R + (k % 5 === 0 ? 20 : 15)
    return <line key={k} x1={CX + r1 * Math.cos(a)} y1={CY - r1 * Math.sin(a)} x2={CX + r2 * Math.cos(a)} y2={CY - r2 * Math.sin(a)}
                 stroke="var(--ink)" strokeWidth={k % 5 === 0 ? 1.4 : 1} />
  })
  const na = Math.PI * (1 - v)
  return (
    <svg width="220" height="124" viewBox="0 0 220 124" role="img" aria-label={`Compliance score ${Math.round(v * 100)} percent`}>
      <path d={`M ${CX - R} ${CY} A ${R} ${R} 0 0 1 ${CX + R} ${CY}`} fill="none" stroke="var(--rule)" strokeWidth="12" />
      <path d={`M ${CX - R} ${CY} A ${R} ${R} 0 0 1 ${CX + R} ${CY}`} fill="none" stroke={`var(--${status === 'compliant' ? 'pass' : status === 'needs_review' ? 'review' : 'fail'}-mark)`}
            strokeWidth="12" strokeDasharray={`${v * len} ${len}`} />
      {ticks}
      <line x1={CX} y1={CY} x2={CX + (R - 18) * Math.cos(na)} y2={CY - (R - 18) * Math.sin(na)} stroke="var(--ink)" strokeWidth="2" strokeLinecap="round" />
      <circle cx={CX} cy={CY} r="5" fill="var(--ink)" />
      <text x={CX - R - 4} y={CY + 18} fontSize="10" fill="var(--ink-3)" textAnchor="middle">0</text>
      <text x={CX + R + 4} y={CY + 18} fontSize="10" fill="var(--ink-3)" textAnchor="middle">100</text>
    </svg>
  )
}

export const rupees = (n, dec = 2) => `₹${Number(n || 0).toLocaleString('en-IN', { minimumFractionDigits: dec, maximumFractionDigits: dec })}`
export const when = (iso) => new Date(iso).toLocaleString('en-IN', { day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' })
export const shortWhen = (iso) => new Date(iso).toLocaleString('en-IN', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit', hour12: false })

// Chart marks use the status "mark" tones; text never wears them.
export const MARK = {
  pass: 'var(--pass-mark)', compliant: 'var(--pass-mark)',
  review: 'var(--review-mark)', needs_review: 'var(--review-mark)',
  missing: 'var(--missing-mark)',
  fail: 'var(--fail-mark)', non_compliant: 'var(--fail-mark)',
}

/** Hover tooltip that follows the pointer. Returns [tooltip element, props for a hover target]. */
export function useTip() {
  const [tip, setTip] = useState(null)
  const bind = (content) => ({
    onMouseMove: (e) => setTip({ x: e.clientX + 12, y: e.clientY + 12, content }),
    onMouseLeave: () => setTip(null),
    onFocus: (e) => { const r = e.currentTarget.getBoundingClientRect(); setTip({ x: r.right + 8, y: r.top, content }) },
    onBlur: () => setTip(null),
    tabIndex: 0,
  })
  const el = tip && <div className="tip" style={{ left: tip.x, top: tip.y }} role="tooltip">{tip.content}</div>
  return [el, bind]
}
