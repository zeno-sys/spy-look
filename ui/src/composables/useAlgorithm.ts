import { ref } from 'vue'
import { apiGet, apiPost, apiPatch, apiDelete } from './useApi'

const API = '/algorithm/admin'

// --------------------------------------------------------------------------- //
// Types
// --------------------------------------------------------------------------- //

export interface AlgorithmTag {
  id: number
  name: string
  color: string
}

export interface ProblemListItem {
  id: number
  title: string
  description_preview: string
  tags: AlgorithmTag[]
  created_at: string | null
  updated_at: string | null
}

export interface ProblemDetail extends ProblemListItem {
  description: string
  solution_code: string
  thought: string
}

export interface ExecuteResult {
  stdout: string
  stderr: string
  exit_code: number
  duration_ms: number
  timed_out: boolean
}

export interface SyntaxErrorItem {
  line: number
  col: number
  end_line: number | null
  end_col: number | null
  message: string
}

export interface ProblemFilters {
  q?: string
  tag_ids?: number[]
  sort?: string
}

// --------------------------------------------------------------------------- //
// State (module-level singletons)
// --------------------------------------------------------------------------- //

const _problems = ref<ProblemListItem[]>([])
const _problemsLoading = ref(false)
const _tags = ref<AlgorithmTag[]>([])
const _tagsLoading = ref(false)
const _executing = ref(false)

// --------------------------------------------------------------------------- //
// Composable
// --------------------------------------------------------------------------- //

export function useAlgorithm() {
  // --- Tags ---

  async function listTags() {
    _tagsLoading.value = true
    try {
      const res = await apiGet<{ items: AlgorithmTag[] }>(`${API}/tags`)
      _tags.value = res.items
    } finally {
      _tagsLoading.value = false
    }
  }

  async function createTag(name: string, color = '#64748b'): Promise<AlgorithmTag> {
    const res = await apiPost<AlgorithmTag>(`${API}/tags`, { name, color })
    await listTags()
    return res
  }

  async function updateTag(id: number, data: { name?: string; color?: string }): Promise<AlgorithmTag> {
    const res = await apiPatch<AlgorithmTag>(`${API}/tags/${id}`, data)
    await listTags()
    return res
  }

  async function deleteTag(id: number): Promise<void> {
    await apiDelete(`${API}/tags/${id}`)
    await listTags()
  }

  // --- Problems ---

  async function listProblems(filters: ProblemFilters = {}) {
    _problemsLoading.value = true
    try {
      const params: Record<string, any> = {}
      if (filters.q) params.q = filters.q
      if (filters.tag_ids && filters.tag_ids.length) params.tag_ids = filters.tag_ids.join(',')
      if (filters.sort) params.sort = filters.sort
      const res = await apiGet<{ items: ProblemListItem[] }>(`${API}/problems`, params)
      _problems.value = res.items
    } finally {
      _problemsLoading.value = false
    }
  }

  async function getProblem(id: number): Promise<ProblemDetail> {
    return await apiGet<ProblemDetail>(`${API}/problems/${id}`)
  }

  async function createProblem(data: {
    title: string
    description?: string
    tag_ids?: number[]
  }): Promise<ProblemDetail> {
    return await apiPost<ProblemDetail>(`${API}/problems`, data)
  }

  async function updateProblem(id: number, data: {
    title?: string
    description?: string
    solution_code?: string
    thought?: string
  }): Promise<ProblemDetail> {
    return await apiPost<ProblemDetail>(`${API}/problems/${id}`, data)
  }

  async function deleteProblem(id: number): Promise<void> {
    await apiDelete(`${API}/problems/${id}`)
  }

  async function setProblemTags(id: number, tagIds: number[]): Promise<ProblemDetail> {
    return await apiPost<ProblemDetail>(`${API}/problems/${id}/tags`, { tag_ids: tagIds })
  }

  async function saveSolution(id: number, solutionCode: string, thought: string): Promise<ProblemDetail> {
    return await updateProblem(id, { solution_code: solutionCode, thought })
  }

  // --- Execution ---

  async function executeCode(code: string, stdin: string): Promise<ExecuteResult> {
    _executing.value = true
    try {
      return await apiPost<ExecuteResult>(`${API}/execute`, { code, stdin })
    } finally {
      _executing.value = false
    }
  }

  // --- Syntax check ---

  async function checkSyntax(code: string): Promise<SyntaxErrorItem[]> {
    const res = await apiPost<{ errors: SyntaxErrorItem[] }>(`${API}/syntax-check`, { code })
    return res.errors || []
  }

  return {
    // state
    problems: _problems,
    problemsLoading: _problemsLoading,
    tags: _tags,
    tagsLoading: _tagsLoading,
    executing: _executing,
    // tags ops
    listTags,
    createTag,
    updateTag,
    deleteTag,
    // problem ops
    listProblems,
    getProblem,
    createProblem,
    updateProblem,
    deleteProblem,
    setProblemTags,
    saveSolution,
    // execution
    executeCode,
    // syntax check
    checkSyntax,
  }
}
