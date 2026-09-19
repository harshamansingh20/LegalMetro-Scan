import { useEffect, useState } from 'react'
import { ArrowRight, LogOut, Scale, ShieldAlert } from 'lucide-react'
import { api, hasToken, setToken } from './api.js'
import ScanPage from './ScanPage.jsx'
import StatsPage from './StatsPage.jsx'
import RulesPage from './RulesPage.jsx'
import RecordsPage from './RecordsPage.jsx'
import ResultView from './ResultView.jsx'
import { Corners, Kicker } from './ui.jsx'

const PAGES = [
  ['scan', 'Packaging scan'],
  ['stats', 'Enforcement stats'],
  ['rules', 'Statutory rules'],
  ['records', 'Scanned records'],
]

const useHash = () => {
  const [hash, setHash] = useState(location.hash)
  useEffect(() => {
    const on = () => { setHash(location.hash); scrollTo(0, 0) }
    addEventListener('hashchange', on)
    return () => removeEventListener('hashchange', on)
  }, [])
  return hash
}

const Wordmark = () => (
  <>
    <span className="brand-mark"><Scale size={22} strokeWidth={1.5} /></span>
    <span className="brand-word">LegalMetro</span>
    <span className="brand-tag">SCAN</span>
  </>
)

export default function App() {
  const [user, setUser] = useState(null)
  const [checking, setChecking] = useState(hasToken())
  const hash = useHash()

  useEffect(() => {
    if (hasToken()) api('/auth/me').then(setUser).catch(() => setToken(null)).finally(() => setChecking(false))
  }, [])

  if (checking) return null
  if (!user) return <Login onLogin={setUser} />

  const detailId = hash.match(/^#\/scans\/(\d+)/)?.[1]
  const page = detailId ? 'records' : PAGES.find(([k]) => hash === `#/${k}`)?.[0] || 'scan'

  return (
    <>
      <header className="topbar">
        <div className="topbar-inner">
          <a href="#/scan" className="brand" aria-label="LegalMetro-Scan home"><Wordmark /></a>
          <nav className="nav" aria-label="Main">
            {PAGES.map(([k, label]) => (
              <a key={k} href={`#/${k}`} className={page === k ? 'active' : ''} aria-current={page === k ? 'page' : undefined}>{label}</a>
            ))}
          </nav>
          <div className="who">
            <div>
              <div className="who-name">{user.name}</div>
              <div className="who-role">{user.role === 'officer' ? 'Inspecting officer' : 'Business self-check'}</div>
            </div>
            <button className="icon-btn" title="Sign out" aria-label="Sign out" onClick={() => { setToken(null); setUser(null) }}><LogOut size={18} /></button>
          </div>
        </div>
      </header>
      <div className="context">
        <div className="context-inner">
          <span><ShieldAlert size={15} />Statutory pre-check · Legal Metrology (Packaged Commodities) Rules, 2011 · S.36 Legal Metrology Act, 2009</span>
          <span>Decision support — the officer decides</span>
        </div>
        <div className="ruler" aria-hidden="true" />
      </div>
      <main>
        {detailId ? <Detail key={detailId} id={detailId} user={user} />
          : page === 'stats' ? <StatsPage />
          : page === 'rules' ? <RulesPage />
          : page === 'records' ? <RecordsPage />
          : <ScanPage user={user} />}
      </main>
    </>
  )
}

function Detail({ id, user }) {
  const [scan, setScan] = useState(null)
  const [err, setErr] = useState('')
  useEffect(() => { api(`/scans/${id}`).then(setScan, (e) => setErr(e.message)) }, [id])
  if (err) return <p className="error page-body" style={{ paddingTop: 36 }}>{err} · <a href="#/records">Back to records</a></p>
  if (!scan) return <p className="muted page-body" style={{ paddingTop: 36 }}>Loading record…</p>
  return <ResultView scan={scan} user={user} onUpdate={setScan} back={['#/records', 'All records']} />
}

function Login({ onLogin }) {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [err, setErr] = useState('')
  const [busy, setBusy] = useState(false)

  const submit = async (e) => {
    e.preventDefault()
    setBusy(true)
    setErr('')
    try {
      const r = await api('/auth/login', { json: { email, password } })
      setToken(r.token)
      onLogin(r.user)
    } catch (e) {
      setErr(e.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="login">
      <section className="login-story">
        <div className="login-brand"><Wordmark /><Kicker>SIH26034 · Prototype</Kicker></div>
        <div className="login-copy">
          <h1>If it’s on the shelf, <span>it should pass the label.</span></h1>
          <p>
            Photograph any packaged product. LegalMetro Scan reads the label with self-hosted OCR and checks it against
            all seven mandatory declarations under the Packaged Commodities Rules — instantly, consistently, at scale.
          </p>
        </div>
        <div className="ruler" aria-hidden="true" />
      </section>
      <div className="login-panel">
        <form className="login-form" onSubmit={submit}>
          <Corners />
          <div>
            <Kicker>Officer &amp; business access</Kicker>
            <h2>Sign in</h2>
          </div>
          <label className="field">Email
            <input className="input" type="email" autoComplete="username" placeholder="name@department.gov.in" value={email} onChange={(e) => setEmail(e.target.value)} required autoFocus />
          </label>
          <label className="field">Password
            <input className="input" type="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} required />
          </label>
          {err && <p className="error" role="alert">{err}</p>}
          <button className="btn primary lg" disabled={busy}>{busy ? 'Signing in…' : <>Sign in <ArrowRight size={18} /></>}</button>
          <p>Officers audit and review every scan. Businesses self-check their own labels before they ship.</p>
        </form>
      </div>
    </div>
  )
}
