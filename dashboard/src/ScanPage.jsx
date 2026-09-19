import { useEffect, useRef, useState } from 'react'
import { ArrowRight, Barcode, ImageUp, Loader2, ScanLine, Upload } from 'lucide-react'
import { api } from './api.js'
import ResultView from './ResultView.jsx'
import { Corners, Kicker } from './ui.jsx'

const ACCEPT = ['image/jpeg', 'image/png', 'image/webp']

function useImageInfo(file) {
  const [info, setInfo] = useState(null)
  useEffect(() => {
    if (!file) return setInfo(null)
    const url = URL.createObjectURL(file)
    const img = new Image()
    img.onload = () => setInfo({ url, w: img.naturalWidth, h: img.naturalHeight })
    img.src = url
    setInfo({ url })
    return () => URL.revokeObjectURL(url)
  }, [file])
  return info
}

function DropZone({ file, onFile, onError, title, hint, kicker, icon: Icon, small }) {
  const input = useRef()
  const [over, setOver] = useState(false)
  const info = useImageInfo(file)
  const take = (f) => f && (ACCEPT.includes(f.type) ? onFile(f) : onError('Use a JPEG, PNG or WebP image'))
  const pick = () => input.current.click()

  return (
    <div
      className={`drop ${small ? 'small' : ''} ${over ? 'over' : ''}`}
      role="button" tabIndex={0} aria-label={file ? `${kicker}: ${file.name}. Press to replace` : title}
      onClick={pick}
      onKeyDown={(e) => (e.key === 'Enter' || e.key === ' ') && (e.preventDefault(), pick())}
      onDragOver={(e) => { e.preventDefault(); setOver(true) }}
      onDragLeave={() => setOver(false)}
      onDrop={(e) => { e.preventDefault(); setOver(false); take(e.dataTransfer.files[0]) }}
    >
      <Corners />
      <input ref={input} type="file" accept={ACCEPT.join(',')} hidden onChange={(e) => { take(e.target.files[0]); e.target.value = '' }} />
      {file ? (
        <div className="drop-filled">
          {info?.url && <img src={info.url} alt="" />}
          <div>
            <Kicker>{kicker} · selected</Kicker>
            <div className="fname" style={{ marginTop: 8 }}>{file.name}</div>
            <div className="fmeta">{info?.w ? `${info.w} × ${info.h} px · ` : ''}{Math.max(1, Math.round(file.size / 1024))} KB</div>
            <div className="actions">
              <button type="button" className="btn" onClick={(e) => { e.stopPropagation(); pick() }}><Upload size={16} /> Replace</button>
              <button type="button" className="btn quiet" onClick={(e) => { e.stopPropagation(); onFile(null) }}>Remove</button>
            </div>
          </div>
        </div>
      ) : (
        <div className="drop-empty">
          <Icon size={30} strokeWidth={1.4} />
          <strong>{title}</strong>
          <div className="hint">{hint}</div>
        </div>
      )}
    </div>
  )
}

export function Running({ what }) {
  return (
    <div className="card progress" role="status">
      <Loader2 className="spin" size={22} />
      <div>
        <b>{what}</b>
        <div className="small muted">PaddleOCR (self-hosted) reads the label → 7 declarations checked → barcode cross-checked. 4–35 s on CPU.</div>
      </div>
    </div>
  )
}

export default function ScanPage({ user }) {
  const [label, setLabel] = useState(null)
  const [barcode, setBarcode] = useState(null)
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')
  const [scan, setScan] = useState(null)
  const [rules, setRules] = useState(null)
  const resultRef = useRef()

  useEffect(() => { api('/rules').then(setRules, () => {}) }, [])

  const run = async () => {
    setBusy(true)
    setErr('')
    setScan(null)
    const fd = new FormData()
    fd.append('file', label)
    if (barcode) fd.append('barcode', barcode)
    try {
      setScan(await api('/scans', { method: 'POST', body: fd }))
      setTimeout(() => resultRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' }), 50)
    } catch (e) {
      setErr(e.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Check a label</h1>
          <p>Upload the declaration panel of a pack. Add a close-up of the barcode to cross-check MRP and net quantity against the product registry.</p>
        </div>
      </div>

      <div className="page-body">
        <div className="drops">
          <DropZone file={label} onFile={setLabel} onError={setErr} icon={ImageUp} kicker="Label photo"
                    title="Drop the label photo here, or click to choose"
                    hint="JPG, PNG or WebP — the principal display panel or the back declaration panel" />
          <DropZone small file={barcode} onFile={setBarcode} onError={setErr} icon={Barcode} kicker="Barcode close-up"
                    title="Barcode close-up (optional)"
                    hint="Barcodes printed on the label are read automatically — this is for a sharper shot" />
        </div>
        <div className="run-bar">
          <button className="btn primary lg" disabled={!label || busy} onClick={run}>
            <ScanLine size={18} /> {busy ? 'Reading label…' : 'Run compliance audit'} {!busy && <ArrowRight size={18} />}
          </button>
          <span className="kicker">PaddleOCR (self-hosted) · 4–35 s per photo on CPU</span>
          {err && <span className="error" role="alert">{err}</span>}
        </div>

        {busy && <div style={{ marginTop: 24 }}><Running what="Reading the label and running the statutory audit…" /></div>}

        {!scan && !busy && rules && (
          <section className="measured">
            <div className="measured-head"><Kicker ink>What gets measured — {rules.fields.length} mandatory declarations</Kicker><span className="kicker">Ruleset {rules.version}</span></div>
            <div className="measured-grid">
              {rules.fields.map((f) => <div key={f.id}><span className="ref">{f.rule_ref}</span>{f.label}</div>)}
            </div>
          </section>
        )}
      </div>

      <div ref={resultRef} style={{ scrollMarginTop: 16 }}>
        {scan && <ResultView scan={scan} user={user} onUpdate={setScan} back={null} />}
      </div>
    </>
  )
}
