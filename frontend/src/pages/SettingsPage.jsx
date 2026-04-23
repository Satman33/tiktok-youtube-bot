import { useEffect, useState } from 'react'
import axios from 'axios'

export default function SettingsPage() {
  const [settings, setSettings] = useState(null)
  const [serviceStatus, setServiceStatus] = useState(null)
  const [limitValue, setLimitValue] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')

  async function fetchData() {
    try {
      setLoading(true)
      setError('')
      const [settingsResponse, statusResponse] = await Promise.all([
        axios.get('/api/settings'),
        axios.get('/api/service-status'),
      ])
      setSettings(settingsResponse.data)
      setLimitValue(String(settingsResponse.data.global_daily_limit))
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

  async function saveLimit(event) {
    event.preventDefault()
    try {
      setError('')
      setMessage('')
      await axios.post('/api/settings/limit', { daily_limit: Number(limitValue) })
      setMessage('Global daily limit updated.')
      await fetchData()
    } catch (err) {
      setError(err.response?.data?.detail || err.message)
    }
  }

  if (loading) return <div className="panel">Loading settings...</div>

  return (
    <div className="page-stack">
      <section className="settings-layout">
        <div className="panel">
          <div className="panel-header">
            <div>
              <h3>Global controls</h3>
              <p className="panel-subtitle">Runtime settings that affect all regular users</p>
            </div>
          </div>

          <form className="form-grid" onSubmit={saveLimit}>
            <input
              className="input"
              type="number"
              min="1"
              max="1000"
              value={limitValue}
              onChange={event => setLimitValue(event.target.value)}
            />
            <button className="button" type="submit">Save limit</button>
          </form>

          {settings ? (
            <div className="list-block" style={{ marginTop: 16 }}>
              <div className="list-row">
                <div>
                  <strong>Current global daily limit</strong>
                  <span className="muted">Applied to all non-VIP users by default</span>
                </div>
                <span>{settings.global_daily_limit}</span>
              </div>
            </div>
          ) : null}

          {message ? <div className="empty-state">{message}</div> : null}
          {error ? <div className="error-state">{error}</div> : null}
        </div>

        <div className="panel">
          <div className="panel-header">
            <div>
              <h3>Environment summary</h3>
              <p className="panel-subtitle">Useful paths and service targets</p>
            </div>
          </div>

          {serviceStatus ? (
            <div className="list-block">
              <div className="list-row">
                <div>
                  <strong>Database URL</strong>
                  <span className="muted">Current backend connection string</span>
                </div>
                <span className="muted" style={{ maxWidth: 240, wordBreak: 'break-word' }}>
                  {serviceStatus.database_url}
                </span>
              </div>
              <div className="list-row">
                <div>
                  <strong>Redis URL</strong>
                  <span className="muted">Configured cache / future queue target</span>
                </div>
                <span className="muted" style={{ maxWidth: 240, wordBreak: 'break-word' }}>
                  {serviceStatus.redis_url}
                </span>
              </div>
              <div className="list-row">
                <div>
                  <strong>Cookies file</strong>
                  <span className="muted">Required for restricted YouTube videos</span>
                </div>
                <span className={`badge ${serviceStatus.cookies_file ? 'success' : 'failed'}`}>
                  {serviceStatus.cookies_file ? 'present' : 'missing'}
                </span>
              </div>
            </div>
          ) : null}
        </div>
      </section>
    </div>
  )
}
