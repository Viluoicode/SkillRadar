import { useEffect, useState } from 'react'
import {
  Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts'
import { api, type Role, type SkillDemand } from '../api'

interface Props {
  onPickSkill: (skill: string) => void
}

export function Dashboard({ onPickSkill }: Props) {
  const [roles, setRoles] = useState<Role[]>([])
  const [roleId, setRoleId] = useState<number | null>(null)
  const [demand, setDemand] = useState<SkillDemand[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    api.getRoles()
      .then((r) => {
        setRoles(r)
        if (r.length > 0) setRoleId(r[0].id)
      })
      .catch((e) => setError(String(e)))
  }, [])

  useEffect(() => {
    if (roleId == null) return
    setLoading(true)
    setError(null)
    api.getSkillDemand(roleId, 15)
      .then(setDemand)
      .catch((e) => setError(String(e)))
      .finally(() => setLoading(false))
  }, [roleId])

  const chartData = demand.map((d) => ({ name: d.skill, count: d.jobCount }))

  return (
    <div className="panel">
      <div className="filters">
        <label className="field">
          Target role
          <select
            value={roleId ?? ''}
            onChange={(e) => setRoleId(Number(e.target.value))}
          >
            {roles.map((r) => (
              <option key={r.id} value={r.id}>{r.name}</option>
            ))}
          </select>
        </label>
      </div>

      {error && <p className="error">{error}</p>}
      {loading && <p className="center">Loading skill demand…</p>}

      {!loading && demand.length === 0 && !error && (
        <p className="center">
          No skill demand yet for this role. Click <strong>Refresh data</strong> to ingest job postings.
        </p>
      )}

      {!loading && demand.length > 0 && (
        <>
          <h3 style={{ marginTop: 0 }}>Most in-demand skills</h3>
          <div style={{ width: '100%', height: 420 }}>
            <ResponsiveContainer>
              <BarChart data={chartData} layout="vertical" margin={{ left: 40, right: 24 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#2c3142" horizontal={false} />
                <XAxis type="number" stroke="#9aa3b2" allowDecimals={false} />
                <YAxis type="category" dataKey="name" width={130} stroke="#9aa3b2" tick={{ fontSize: 12 }} />
                <Tooltip
                  contentStyle={{ background: '#1a1d27', border: '1px solid #2c3142', borderRadius: 8 }}
                  cursor={{ fill: 'rgba(91,140,255,0.08)' }}
                />
                <Bar dataKey="count" fill="#5b8cff" radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>

          <p className="muted" style={{ fontSize: 13 }}>
            Click a skill to see matching jobs:
          </p>
          <div className="job skills" style={{ borderTop: 'none' }}>
            {demand.map((d) => (
              <button
                key={d.skillId}
                className="chip"
                style={{ cursor: 'pointer' }}
                onClick={() => onPickSkill(d.skill)}
              >
                {d.skill} · {d.jobCount}
              </button>
            ))}
          </div>
        </>
      )}
    </div>
  )
}
