import { useCallback, useEffect, useState } from 'react'
import { api, type Stats } from './api'
import { Dashboard } from './components/Dashboard'
import { JobsView } from './components/JobsView'

type Tab = 'dashboard' | 'jobs'

function App() {
  const [tab, setTab] = useState<Tab>('dashboard')
  const [stats, setStats] = useState<Stats | null>(null)
  const [skillFilter, setSkillFilter] = useState('')
  const [refreshing, setRefreshing] = useState(false)
  const [notice, setNotice] = useState<string | null>(null)

  const loadStats = useCallback(() => {
    api.getStats().then(setStats).catch(() => {})
  }, [])

  useEffect(() => { loadStats() }, [loadStats])

  const refresh = async () => {
    setRefreshing(true)
    setNotice(null)
    try {
      await api.triggerIngest()
      setNotice('Ingestion started in the background. Data will update shortly — reload in a minute.')
    } catch (e) {
      setNotice(`Could not start ingestion: ${e}`)
    } finally {
      setRefreshing(false)
      setTimeout(loadStats, 1500)
    }
  }

  const pickSkill = (skill: string) => {
    setSkillFilter(skill)
    setTab('jobs')
  }

  return (
    <div className="app">
      <header className="app-header">
        <div className="brand">
          <h1>SkillRadar</h1>
          <span className="tag">job-market intelligence</span>
        </div>
        <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
          <div className="stats-row">
            <div className="stat">
              <div className="num">{stats ? stats.activeJobs.toLocaleString() : '—'}</div>
              <div className="label">active jobs</div>
            </div>
            <div className="stat">
              <div className="num">{stats ? stats.totalSkills : '—'}</div>
              <div className="label">skills tracked</div>
            </div>
            <div className="stat">
              <div className="num">{stats?.lastRunStatus ?? '—'}</div>
              <div className="label">
                last run{stats?.lastRunAt ? ` · ${new Date(stats.lastRunAt).toLocaleString()}` : ''}
              </div>
            </div>
          </div>
          <button onClick={refresh} disabled={refreshing}>
            {refreshing ? 'Starting…' : 'Refresh data'}
          </button>
        </div>
      </header>

      {notice && <p className="muted" style={{ marginTop: -8 }}>{notice}</p>}

      <nav className="tabs">
        <button className={tab === 'dashboard' ? 'active' : ''} onClick={() => setTab('dashboard')}>
          Dashboard
        </button>
        <button className={tab === 'jobs' ? 'active' : ''} onClick={() => setTab('jobs')}>
          Jobs
        </button>
      </nav>

      {tab === 'dashboard'
        ? <Dashboard onPickSkill={pickSkill} />
        : <JobsView skill={skillFilter} onSkillChange={setSkillFilter} />}
    </div>
  )
}

export default App
