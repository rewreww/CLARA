// One fixed UTC day offset per patient preserves exact chart-event intervals.
// Display conversion only: never mutate underlying source rows or admission IDs.
const SHIFTED_DATE = /(?<!\d)(?:21\d{2}|2200)-(?:0[1-9]|1[0-2])-(?:0[1-9]|[12]\d|3[01])(?!\d)/g
export function demoDateText(value, offsetDays) {
  if (typeof value !== 'string' || !Number.isInteger(offsetDays) || Math.abs(offsetDays) > 100000) return value
  return value.replace(SHIFTED_DATE, raw => {
    const [y, m, d] = raw.split('-').map(Number)
    const ms = Date.UTC(y, m - 1, d)
    const valid = new Date(ms)
    if (valid.getUTCFullYear() !== y || valid.getUTCMonth() !== m - 1 || valid.getUTCDate() !== d) return raw
    const result = new Date(ms + offsetDays * 86400000)
    if (!Number.isFinite(result.getTime())) return raw
    return result.toISOString().slice(0, 10)
  })
}
