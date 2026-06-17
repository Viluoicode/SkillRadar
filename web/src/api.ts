// Typed client for the SkillRadar .NET API. All paths are same-origin (Vite proxies /api).

export interface Role {
  id: number
  name: string
}

export interface SkillDemand {
  skillId: number
  skill: string
  category: string
  jobCount: number
}

export interface Job {
  id: number
  company: string
  title: string
  location: string | null
  remote: boolean
  source: string
  applyUrl: string
  postedAt: string | null
  skills: string[]
}

export interface JobList {
  total: number
  page: number
  pageSize: number
  items: Job[]
}

export interface Stats {
  activeJobs: number
  totalSkills: number
  roles: number
  lastRunAt: string | null
  lastRunStatus: string | null
}

export interface JobFilters {
  skill?: string
  source?: string
  company?: string
  location?: string
  remote?: boolean
  search?: string
  page?: number
  pageSize?: number
}

async function getJson<T>(url: string): Promise<T> {
  const res = await fetch(url)
  if (!res.ok) throw new Error(`Request failed: ${res.status} ${res.statusText}`)
  return res.json() as Promise<T>
}

export const api = {
  getStats: () => getJson<Stats>('/api/stats'),
  getRoles: () => getJson<Role[]>('/api/roles'),
  getSkillDemand: (roleId: number, top = 20) =>
    getJson<SkillDemand[]>(`/api/skill-demand?role=${roleId}&top=${top}`),

  getJobs: (filters: JobFilters) => {
    const params = new URLSearchParams()
    if (filters.skill) params.set('skill', filters.skill)
    if (filters.source) params.set('source', filters.source)
    if (filters.company) params.set('company', filters.company)
    if (filters.location) params.set('location', filters.location)
    if (filters.remote !== undefined) params.set('remote', String(filters.remote))
    if (filters.search) params.set('search', filters.search)
    params.set('page', String(filters.page ?? 1))
    params.set('pageSize', String(filters.pageSize ?? 25))
    return getJson<JobList>(`/api/jobs?${params.toString()}`)
  },

  triggerIngest: async (): Promise<{ jobId: string }> => {
    const res = await fetch('/api/ingest', { method: 'POST' })
    if (!res.ok) throw new Error(`Ingest failed: ${res.status}`)
    return res.json()
  },
}
