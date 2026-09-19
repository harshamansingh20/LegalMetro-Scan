// "Rs. 1,299.00" -> 1299 ; "53,00" (OCR comma decimal) -> 53. Mirrors backend/app/pipeline/units.py money().
export function money(text) {
  const m = String(text || '').match(/(\d+,\d{1,2}(?!\d)|\d+(?:,\d{3})*(?:\.\d+)?)/)
  if (!m) return null
  const s = m[1]
  return Number(/^\d+,\d{1,2}$/.test(s) ? s.replace(',', '.') : s.replace(/,/g, ''))
}
