import { ref } from 'vue'
import { apiGet, apiPost, apiPatch, apiDelete } from './useApi'

const API = '/bookmarks/admin/read-later'

export interface ReadLaterItem {
  id: number
  url: string
  title: string
  summary: string
  status: 'pending' | 'read' | 'archived'
  bookmark_id: number | null
  created_at: string | null
  updated_at: string | null
}

const _items = ref<ReadLaterItem[]>([])
const _loading = ref(false)

export function useReadLater() {
  async function listItems(status?: string, q?: string) {
    _loading.value = true
    try {
      const params: Record<string, any> = {}
      if (status) params.status = status
      if (q) params.q = q
      const res = await apiGet<{ items: ReadLaterItem[] }>(API, params)
      _items.value = res.items
    } finally {
      _loading.value = false
    }
  }

  async function getItem(id: number): Promise<ReadLaterItem> {
    return await apiGet<ReadLaterItem>(`${API}/${id}`)
  }

  async function createItem(data: {
    url: string
    title?: string
    summary?: string
    bookmark_id?: number | null
  }): Promise<ReadLaterItem> {
    const item = await apiPost<ReadLaterItem>(API, data)
    await listItems()
    return item
  }

  async function updateItem(
    id: number,
    data: {
      title?: string
      summary?: string
      status?: string
      bookmark_id?: number | null
    }
  ): Promise<ReadLaterItem> {
    const item = await apiPatch<ReadLaterItem>(`${API}/${id}`, data)
    await listItems()
    return item
  }

  async function deleteItem(id: number): Promise<void> {
    await apiDelete(`${API}/${id}`)
    await listItems()
  }

  async function markAsRead(id: number): Promise<ReadLaterItem> {
    return await updateItem(id, { status: 'read' })
  }

  async function archive(id: number): Promise<ReadLaterItem> {
    return await updateItem(id, { status: 'archived' })
  }

  return {
    items: _items,
    loading: _loading,
    listItems,
    getItem,
    createItem,
    updateItem,
    deleteItem,
    markAsRead,
    archive,
  }
}
