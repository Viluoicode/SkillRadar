import { useEffect, useState } from 'react'
import { api, type JobList } from '../api'

interface Props {
  skill: string
  onSkillChange: (skill: string) => void
}

const SOURCES = ['', 'Greenhouse', 'Lever', 'Ashby']
const PAGE_SIZE = 25

export function JobsView({ skill, onSkillChange }: Props) {
  const [search, setSearch] = useState('')
  const [source, setSource] = useState('')
  const [remoteOnly, setRemoteOnly] = useState(false)
  const [page, setPage] = useState(1)
  const [data, setData] = useState<JobList | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Reset to page 1 whenever a filter changes.
  useEffect(() => { setPage(1) }, [skill, search, source, remoteOnly])

  useEffect(() => {
    setLoading(true)
    setError(null)
    const handle = setTimeout(() => {
      api.getJobs({
        skill: skill || undefined,
        source: source || undefined,
        search: search || undefined,
        remote: remoteOnly ? true : undefined,
        page,
        pageSize: PAGE_SIZE,
      })
        .then(setData)
        .catch((e) => setError(String(e)))
        .finally(() => setLoading(false))
    }, 250) // debounce text input
    return () => clearTimeout(handle)
  }, [skill, search, source, remoteOnly, page])

  const totalPages = data ? Math.max(1, Math.ceil(data.total / data.pageSize)) : 1

  return (
    <div className="panel">
      <div className="filters">
        <label className="field">
          Search title
          <input
            type="text"
            placeholder="e.g. backend engineer"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </label>
        <label className="field">
          Skill
          <input
            type="text"
            placeholder="e.g. Kubernetes"
            value={skill}
            onChange={(e) => onSkillChange(e.target.value)}
          />
        </label>
        <label className="field">
          Source
          <select value={source} onChange={(e) => setSource(e.target.value)}>
            {SOURCES.map((s) => (
              <option key={s} value={s}>{s || 'All sources'}</option>
            ))}
          </select>
        </label>
        <label className="field checkbox">
          <input
            type="checkbox"
            checked={remoteOnly}
            onChange={(e) => setRemoteOnly(e.target.checked)}
          />
          Remote only
        </label>
      </div>

      {error && <p className="error">{error}</p>}
      {loading && <p className="center">Loading jobs…</p>}

      {!loading && data && (
        <>
          <p className="muted" style={{ fontSize: 13 }}>
            {data.total.toLocaleString()} matching job{data.total === 1 ? '' : 's'}
          </p>

          {data.items.length === 0 && <p className="center">No jobs match these filters.</p>}

          {data.items.map((job) => (
            <div className="job" key={job.id}>
              <div>
                <div className="title">{job.title}</div>
                <div className="meta">
                  {job.company}
                  {job.location ? ` · ${job.location}` : ''}
                  {' · '}
                  <span className="badge">{job.source}</span>
                  {job.remote && <span className="badge remote" style={{ marginLeft: 6 }}>Remote</span>}
                </div>
                {job.skills.length > 0 && (
                  <div className="skills">
                    {job.skills.slice(0, 12).map((s) => (
                      <span className="chip" key={s}>{s}</span>
                    ))}
                  </div>
                )}
              </div>
              <div className="apply">
                <a href={job.applyUrl} target="_blank" rel="noopener noreferrer">Apply ↗</a>
              </div>
            </div>
          ))}

          {data.total > data.pageSize && (
            <div className="pager">
              <button
                className="secondary"
                disabled={page <= 1}
                onClick={() => setPage((p) => p - 1)}
              >
                ← Prev
              </button>
              <span className="muted">Page {page} of {totalPages}</span>
              <button
                className="secondary"
                disabled={page >= totalPages}
                onClick={() => setPage((p) => p + 1)}
              >
                Next →
              </button>
            </div>
          )}
        </>
      )}
    </div>
  )
}
