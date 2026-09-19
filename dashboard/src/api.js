// Base URL of the backend. Dev uses the Vite proxy; set VITE_API_URL for a deployed build.
const BASE = import.meta.env.VITE_API_URL || '/api'

let token = sessionStorage.getItem('token')
export const setToken = (t) => {
  token = t
  t ? sessionStorage.setItem('token', t) : sessionStorage.removeItem('token')
}
export const hasToken = () => !!token

export async function api(path, { json, raw, ...opts } = {}) {
  const headers = { ...(token && { Authorization: `Bearer ${token}` }) }
  if (json) {
    headers['Content-Type'] = 'application/json'
    opts.body = JSON.stringify(json)
    opts.method ||= 'POST'
  }
  const res = await fetch(BASE + path, { ...opts, headers })
  if (res.status === 401 && token) {
    setToken(null)
    location.reload()
  }
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error(typeof body.detail === 'string' ? body.detail : `Request failed (${res.status})`)
  }
  return raw ? res.blob() : res.json()
}

export async function download(path, filename) {
  const url = URL.createObjectURL(await api(path, { raw: true }))
  const a = Object.assign(document.createElement('a'), { href: url, download: filename })
  a.click()
  URL.revokeObjectURL(url)
}
