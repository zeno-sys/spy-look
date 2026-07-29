import { ref } from 'vue'
import { apiGet, apiPost, apiPatch, apiDelete } from './useApi'

const API = '/bookmarks/admin'

// --------------------------------------------------------------------------- //
// Types
// --------------------------------------------------------------------------- //

export interface GroupItem {
  id: number
  name: string
  sort_order: number
  bookmark_count?: number
  created_at: string | null
  updated_at: string | null
}

export interface TagItem {
  id: number
  name: string
  color: string
}

export interface BookmarkItem {
  id: number
  url: string
  title: string
  favicon_url: string
  group_id: number | null
  pinned: boolean
  access_count: number
  last_accessed_at: string | null
  created_at: string | null
  updated_at: string | null
  tags: TagItem[]
  access_count_7d?: number
}

export interface FetchMetadataResult {
  title: string
  favicon_url: string
  error?: string
}

// --------------------------------------------------------------------------- //
// Groups
// --------------------------------------------------------------------------- //

const _groups = ref<GroupItem[]>([])
const _groupsLoading = ref(false)

export function useGroups() {
  async function listGroups() {
    _groupsLoading.value = true
    try {
      const res = await apiGet<{ items: GroupItem[] }>(`${API}/groups`)
      _groups.value = res.items
    } finally {
      _groupsLoading.value = false
    }
  }

  async function createGroup(name: string, sortOrder = 0): Promise<GroupItem> {
    const res = await apiPost<GroupItem>(`${API}/groups`, { name, sort_order: sortOrder })
    await listGroups()
    return res
  }

  async function updateGroup(id: number, data: { name?: string; sort_order?: number }): Promise<GroupItem> {
    const res = await apiPatch<GroupItem>(`${API}/groups/${id}`, data)
    await listGroups()
    return res
  }

  async function deleteGroup(id: number): Promise<void> {
    await apiDelete(`${API}/groups/${id}`)
    await listGroups()
  }

  return {
    groups: _groups,
    groupsLoading: _groupsLoading,
    listGroups,
    createGroup,
    updateGroup,
    deleteGroup,
  }
}

// --------------------------------------------------------------------------- //
// Tags
// --------------------------------------------------------------------------- //

const _tags = ref<TagItem[]>([])
const _tagsLoading = ref(false)

export function useTags() {
  async function listTags() {
    _tagsLoading.value = true
    try {
      const res = await apiGet<{ items: TagItem[] }>(`${API}/tags`)
      _tags.value = res.items
    } finally {
      _tagsLoading.value = false
    }
  }

  async function createTag(name: string, color = '#64748b'): Promise<TagItem> {
    const res = await apiPost<TagItem>(`${API}/tags`, { name, color })
    await listTags()
    return res
  }

  async function updateTag(id: number, data: { name?: string; color?: string }): Promise<TagItem> {
    const res = await apiPatch<TagItem>(`${API}/tags/${id}`, data)
    await listTags()
    return res
  }

  async function deleteTag(id: number): Promise<void> {
    await apiDelete(`${API}/tags/${id}`)
    await listTags()
  }

  return {
    tags: _tags,
    tagsLoading: _tagsLoading,
    listTags,
    createTag,
    updateTag,
    deleteTag,
  }
}

// --------------------------------------------------------------------------- //
// Bookmarks
// --------------------------------------------------------------------------- //

const _bookmarks = ref<BookmarkItem[]>([])
const _pinned = ref<BookmarkItem[]>([])
const _top5 = ref<BookmarkItem[]>([])
const _bookmarksLoading = ref(false)

export interface BookmarkFilters {
  q?: string
  group_id?: number | null
  tag_ids?: number[]
  pinned_only?: boolean
}

export function useBookmarks() {
  async function listBookmarks(filters: BookmarkFilters = {}) {
    _bookmarksLoading.value = true
    try {
      const params: Record<string, any> = {}
      if (filters.q) params.q = filters.q
      if (filters.group_id !== undefined && filters.group_id !== null) params.group_id = filters.group_id
      if (filters.tag_ids && filters.tag_ids.length) params.tag_ids = filters.tag_ids.join(',')
      if (filters.pinned_only) params.pinned_only = true
      const res = await apiGet<{ items: BookmarkItem[] }>(`${API}/bookmarks`, params)
      _bookmarks.value = res.items
    } finally {
      _bookmarksLoading.value = false
    }
  }

  async function listPinned() {
    const res = await apiGet<{ items: BookmarkItem[] }>(`${API}/bookmarks`, { pinned_only: true })
    _pinned.value = res.items
  }

  async function getTop5() {
    const res = await apiGet<{ items: BookmarkItem[] }>(`${API}/bookmarks/top5`)
    _top5.value = res.items
  }

  async function createBookmark(data: {
    url: string
    title?: string
    favicon_url?: string
    group_id?: number | null
  }): Promise<BookmarkItem> {
    return await apiPost<BookmarkItem>(`${API}/bookmarks`, data)
  }

  async function updateBookmark(id: number, data: {
    title?: string
    favicon_url?: string
    group_id?: number | null
    pinned?: boolean
  }): Promise<BookmarkItem> {
    return await apiPatch<BookmarkItem>(`${API}/bookmarks/${id}`, data)
  }

  async function deleteBookmark(id: number): Promise<void> {
    await apiDelete(`${API}/bookmarks/${id}`)
  }

  async function setBookmarkTags(id: number, tagIds: number[]): Promise<BookmarkItem> {
    return await apiPost<BookmarkItem>(`${API}/bookmarks/${id}/tags`, { tag_ids: tagIds })
  }

  async function recordAccess(id: number): Promise<void> {
    try {
      await apiPost(`${API}/bookmarks/${id}/access`)
    } catch {
      // fire-and-forget — don't block the user
    }
  }

  async function fetchMetadata(url: string): Promise<FetchMetadataResult> {
    return await apiPost<FetchMetadataResult>(`${API}/bookmarks/fetch-metadata`, { url })
  }

  async function refreshAll(filters: BookmarkFilters = {}) {
    await Promise.all([
      listBookmarks(filters),
      listPinned(),
      getTop5(),
    ])
  }

  return {
    bookmarks: _bookmarks,
    pinned: _pinned,
    top5: _top5,
    bookmarksLoading: _bookmarksLoading,
    listBookmarks,
    listPinned,
    getTop5,
    createBookmark,
    updateBookmark,
    deleteBookmark,
    setBookmarkTags,
    recordAccess,
    fetchMetadata,
    refreshAll,
  }
}
