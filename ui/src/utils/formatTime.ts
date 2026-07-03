const BEIJING_TZ = 'Asia/Shanghai'

/** 将 API 返回的 UTC 时间格式化为北京时间 YYYY-MM-DD HH:mm:ss */
export function formatBeijingTime(value: string | null | undefined): string {
  if (value == null || value === '') return ''

  const raw = String(value).trim()
  let date: Date

  if (/[zZ]$/.test(raw) || /[+-]\d{2}:?\d{2}$/.test(raw)) {
    date = new Date(raw)
  } else {
    const normalized = raw.includes('T') ? raw : raw.replace(' ', 'T')
    date = new Date(`${normalized}Z`)
  }

  if (Number.isNaN(date.getTime())) return raw

  const parts = new Intl.DateTimeFormat('en-CA', {
    timeZone: BEIJING_TZ,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  }).formatToParts(date)

  const pick = (type: Intl.DateTimeFormatPartTypes) =>
    parts.find((p) => p.type === type)?.value ?? ''

  return `${pick('year')}-${pick('month')}-${pick('day')} ${pick('hour')}:${pick('minute')}:${pick('second')}`
}
