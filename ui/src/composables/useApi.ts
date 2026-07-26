const BASE = ''

const defaultFetchInit: RequestInit = {
  credentials: 'include',
}

async function readErrorMessage(res: Response): Promise<string> {
  const err = await res.json().catch(() => ({ detail: res.statusText }))
  if (typeof err.detail === 'string') return err.detail
  if (err.error?.message) return String(err.error.message)
  if (err.detail != null) return JSON.stringify(err.detail)
  return res.statusText || '请求失败'
}

export async function apiGet<T = any>(path: string, params?: Record<string, any>): Promise<T> {
  const url = new URL(BASE + path, window.location.origin)
  if (params) {
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined && v !== null && v !== '') url.searchParams.set(k, String(v))
    })
  }
  const res = await fetch(url.toString(), { ...defaultFetchInit })
  if (!res.ok) {
    throw new Error(await readErrorMessage(res))
  }
  return res.json()
}

export async function apiPost<T = any>(path: string, body?: any): Promise<T> {
  const res = await fetch(BASE + path, {
    ...defaultFetchInit,
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: body ? JSON.stringify(body) : undefined,
  })
  if (!res.ok) {
    throw new Error(await readErrorMessage(res))
  }
  return res.json()
}

export async function apiPatch<T = any>(path: string, body?: any): Promise<T> {
  // Use POST: peanut-shell / some WAFs drop PATCH and return ERR_EMPTY_RESPONSE
  const res = await fetch(BASE + path, {
    ...defaultFetchInit,
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-HTTP-Method-Override': 'PATCH',
    },
    body: body ? JSON.stringify(body) : undefined,
  })
  if (!res.ok) {
    throw new Error(await readErrorMessage(res))
  }
  return res.json()
}

export async function apiDelete<T = any>(path: string): Promise<T> {
  const res = await fetch(BASE + path, { ...defaultFetchInit, method: 'DELETE' })
  if (!res.ok) {
    throw new Error(await readErrorMessage(res))
  }
  return res.json()
}

export interface DownloadResult {
  blob: Blob
  filename: string
}

function filenameFromDisposition(header: string | null): string | null {
  if (!header) return null
  const utf8 = /filename\*\s*=\s*UTF-8''([^;]+)/i.exec(header)
  if (utf8?.[1]) {
    try {
      return decodeURIComponent(utf8[1].trim().replace(/^"|"$/g, ''))
    } catch {
      return utf8[1].trim().replace(/^"|"$/g, '')
    }
  }
  const plain = /filename\s*=\s*("?)([^";]+)\1/i.exec(header)
  return plain?.[2]?.trim() || null
}

/** GET 并下载二进制响应（如 zip） */
export async function apiDownloadGet(
  path: string,
  params?: Record<string, any>,
  fallbackFilename = 'download.bin',
): Promise<DownloadResult> {
  const url = new URL(BASE + path, window.location.origin)
  if (params) {
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined && v !== null && v !== '') url.searchParams.set(k, String(v))
    })
  }
  const res = await fetch(url.toString(), { ...defaultFetchInit })
  if (!res.ok) {
    throw new Error(await readErrorMessage(res))
  }
  const blob = await res.blob()
  const filename =
    filenameFromDisposition(res.headers.get('Content-Disposition')) || fallbackFilename
  return { blob, filename }
}

/** POST 并下载二进制响应（如 DOCX） */
export async function apiDownloadPost(
  path: string,
  body: FormData | object,
  fallbackFilename = 'download.bin',
): Promise<DownloadResult> {
  const isFormData = body instanceof FormData
  const res = await fetch(BASE + path, {
    ...defaultFetchInit,
    method: 'POST',
    headers: isFormData ? undefined : { 'Content-Type': 'application/json' },
    body: isFormData ? body : JSON.stringify(body),
  })
  if (!res.ok) {
    throw new Error(await readErrorMessage(res))
  }
  const blob = await res.blob()
  const filename =
    filenameFromDisposition(res.headers.get('Content-Disposition')) || fallbackFilename
  return { blob, filename }
}

export type SseHandler = (event: string, data: Record<string, unknown>) => void

export async function apiStreamPost(
  path: string,
  body: FormData | object,
  onEvent: SseHandler,
): Promise<void> {
  const isFormData = body instanceof FormData
  const res = await fetch(BASE + path, {
    ...defaultFetchInit,
    method: 'POST',
    headers: isFormData ? undefined : { 'Content-Type': 'application/json' },
    body: isFormData ? body : JSON.stringify(body),
  })
  if (!res.ok) {
    throw new Error(await readErrorMessage(res))
  }
  if (!res.body) {
    throw new Error('响应不支持流式读取')
  }

  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    const blocks = buffer.split('\n\n')
    buffer = blocks.pop() ?? ''
    for (const block of blocks) {
      if (!block.trim()) continue
      let event = 'message'
      let dataStr = ''
      for (const line of block.split('\n')) {
        if (line.startsWith('event:')) event = line.slice(6).trim()
        else if (line.startsWith('data:')) dataStr = line.slice(5).trim()
      }
      if (dataStr) {
        try {
          onEvent(event, JSON.parse(dataStr))
        } catch {
          onEvent(event, { raw: dataStr })
        }
      }
    }
  }
}
