import { ref } from 'vue'
import { apiGet, apiPost, apiDelete } from './useApi'

const API = '/bookmarks/admin/web-clips'

export interface WebClipSummary {
  id: number
  url: string
  title: string
  bookmark_id: number | null
  fetched_at: string | null
}

export interface WebClipFull extends WebClipSummary {
  content_md: string
  content_html: string
  extract_error?: string
}

const _clips = ref<WebClipSummary[]>([])
const _loading = ref(false)

export function useWebClips() {
  async function listClips(q?: string, limit = 50, offset = 0) {
    _loading.value = true
    try {
      const params: Record<string, any> = { limit, offset }
      if (q) params.q = q
      const res = await apiGet<{ items: WebClipSummary[] }>(API, params)
      _clips.value = res.items
    } finally {
      _loading.value = false
    }
  }

  async function getClip(id: number): Promise<WebClipFull> {
    return await apiGet<WebClipFull>(`${API}/${id}`)
  }

  async function clipUrl(url: string, bookmarkId?: number | null): Promise<WebClipFull> {
    const data: Record<string, any> = { url }
    if (bookmarkId !== undefined) data.bookmark_id = bookmarkId
    const clip = await apiPost<WebClipFull>(API, data)
    await listClips()
    return clip
  }

  async function deleteClip(id: number): Promise<void> {
    await apiDelete(`${API}/${id}`)
    await listClips()
  }

  return {
    clips: _clips,
    loading: _loading,
    listClips,
    getClip,
    clipUrl,
    deleteClip,
  }
}
