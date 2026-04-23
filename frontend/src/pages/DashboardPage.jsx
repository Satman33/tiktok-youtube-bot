import { useEffect, useState } from 'react'
import axios from 'axios'

function formatNumber(value) {
  return new Intl.NumberFormat().format(value ?? 0)
}

function formatPercent(value) {
  return `${value ?? 0}%`
}

export default function DashboardPage() {
  const [stats, setStats] = useState(null)
  const [serviceStatus, setServiceStatus] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  async function fetchData() {
    try {
      setLoading(true)
      setError('')
      const [statsResponse, statusResponse] = await Promise.all([
        axios.get('/api/stats'),
        axios.get('/api/service-status'),
      ])
      setStats(statsResponse.data)
      setServiceStatus(statusResponse.data)
    } catch (err) {
      setError(err.response?.data?.detail || err.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchData()
  }, [])

  if (loading) return <div className="panel">Loading dashboard...</div>
  if (error) return <div className="error-state">{error}</div>
  if (!stats || !serviceStatus) return <div className="empty-state">No data</div>

  const maxTrend = Math.max(...stats.recent_trend.map(item => item.downloads), 1)

  return (
    <div className="page-stack">
      <section className="stats-grid">
        <article className="stat-card">
          <p>Total users</p>
          <div className="stat-value">{formatNumber(stats.total_users)}</div>
        </article>
        <article className="stat-card">
          <p>Total downloads</p>
          <div className="stat-value">{formatNumber(stats.total_downloads)}</div>
        </article>
        <article className="stat-card">
          <p>Today's downloads</p>
          <div className="stat-value">{formatNumber(stats.today_downloads)}</div>
        </article>
        <article className="stat-card">
          <p>Success rate</p>
          <div className="stat-value">{formatPercent(stats.success_rate)}</div>
        </article>
      </section>

      <section className="grid-two">
        <div className="panel">
          <div className="panel-header">
            <div>
              <h3>Service status</h3>
              <p className="panel-subtitle">Runtime checks for core dependencies</p>
            </div>
            <button className="button-secondary" onClick={fetchData}>Refresh</button>
          </div>

          <div className="status-grid">
            <div className="stat-card">
              <h4>API</h4>
              <div className={`badge ${serviceStatus.api}`}>{serviceStatus.api}</div>
            </div>
            <div className="stat-card">
              <h4>Database</h4>
              <div className={`badge ${serviceStatus.database}`}>{serviceStatus.database}</div>
            </div>
            <div className="stat-card">
              <h4>Cookies</h4>
              <div className={`badge ${serviceStatus.cookies_file ? 'success' : 'failed'}`}>
                {serviceStatus.cookies_file ? 'present' : 'missing'}
              </div>
            </div>
            <div className="stat-card">
              <h4>yt-dlp CLI</h4>
              <div className={`badge ${serviceStatus.yt_dlp_available ? 'success' : 'failed'}`}>
                {serviceStatus.yt_dlp_available ? 'available' : 'missing'}
              </div>
            </div>
            <div className="stat-card">
              <h4>Node.js</h4>
              <div className={`badge ${serviceStatus.node_available ? 'success' : 'failed'}`}>
                {serviceStatus.node_available ? 'available' : 'missing'}
              </div>
            </div>
            <div className="stat-card">
              <h4>Redis</h4>
              <div className={`badge ${serviceStatus.redis_configured ? 'success' : 'failed'}`}>
                {serviceStatus.redis_configured ? 'configured' : 'not set'}
              </div>
            </div>
          </div>
        </div>

        <div className="panel">
          <div className="panel-header">
            <div>
              <h3>Account health</h3>
              <p className="panel-subtitle">Moderation and power-user overview</p>
            </div>
          </div>

          <div className="list-block">
            <div className="list-row">
              <div>
                <strong>Last 7 days</strong>
                <span className="muted">Recent activity volume</span>
              </div>
              <span>{formatNumber(stats.last_7_days_downloads)}</span>
            </div>
            <div className="list-row">
              <div>
                <strong>Last 30 days</strong>
                <span className="muted">Broader demand trend</span>
              </div>
              <span>{formatNumber(stats.last_30_days_downloads)}</span>
            </div>
            <div className="list-row">
              <div>
                <strong>Banned users</strong>
                <span className="muted">Accounts blocked from bot usage</span>
              </div>
              <span>{formatNumber(stats.banned_users)}</span>
            </div>
            <div className="list-row">
              <div>
                <strong>VIP users</strong>
                <span className="muted">Accounts with extended limits</span>
              </div>
              <span>{formatNumber(stats.vip_users)}</span>
            </div>
          </div>
        </div>
      </section>

      <section className="grid-two">
        <div className="panel">
          <div className="panel-header">
            <div>
              <h3>Top users</h3>
              <p className="panel-subtitle">Most active downloaders across all time</p>
            </div>
          </div>

          <div className="list-block">
            {stats.top_users.length === 0 ? (
              <div className="empty-state">No downloads recorded yet.</div>
            ) : (
              stats.top_users.map(user => (
                <div key={user.telegram_id} className="list-row">
                  <div>
                    <strong>{user.telegram_id}</strong>
                    <span className="muted">Telegram account</span>
                  </div>
                  <span>{formatNumber(user.downloads)} downloads</span>
                </div>
              ))
            )}
          </div>
        </div>

        <div className="panel">
          <div className="panel-header">
            <div>
              <h3>7-day trend</h3>
              <p className="panel-subtitle">Daily download totals</p>
            </div>
          </div>

          <div className="trend-list">
            {stats.recent_trend.length === 0 ? (
              <div className="empty-state">No trend data yet.</div>
            ) : (
              stats.recent_trend.map(item => (
                <div key={item.date} className="list-row">
                  <div style={{ minWidth: 110 }}>
                    <strong>{new Date(item.date).toLocaleDateString()}</strong>
                    <span className="muted">{formatNumber(item.downloads)} downloads</span>
                  </div>
                  <div style={{ flex: 1 }}>
                    <div className="trend-bar">
                      <span style={{ width: `${(item.downloads / maxTrend) * 100}%` }} />
                    </div>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      </section>
    </div>
  )
}
