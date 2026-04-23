import { useEffect, useState } from 'react'
import axios from 'axios'

const DEFAULT_FILTERS = {
  search: '',
  platform: '',
  status: '',
}

function buildQuery(page, filters) {
  const params = new URLSearchParams({
    page: String(page),
    page_size: '12',
  })

  if (filters.search) params.set('search', filters.search)
  if (filters.platform) params.set('platform', filters.platform)
  if (filters.status) params.set('status', filters.status)
  return params.toString()
}

export default function ActivityPage() {
  const [downloadsData, setDownloadsData] = useState({ items: [], total: 0, page: 1, page_size: 12 })
  const [filters, setFilters] = useState(DEFAULT_FILTERS)
  const [page, setPage] = useState(1)
  const [testUrl, setTestUrl] = useState('')
  const [testResult, setTestResult] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  async function fetchDownloads(nextPage = page, nextFilters = filters) {
    try {
      setLoading(true)
      setError('')
      const response = await axios.get(`/api/downloads?${buildQuery(nextPage, nextFilters)}`)
      setDownloadsData(response.data)
    } catch (err) {
      setError(err.response?.data?.detail || err.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchDownloads(1, filters)
  }, [])

  async function runTest(event) {
    event.preventDefault()
    try {
      setError('')
      const response = await axios.post('/api/downloads/test', { url: testUrl })
      setTestResult(response.data)
    } catch (err) {
      setError(err.response?.data?.detail || err.message)
    }
  }

  const totalPages = Math.max(1, Math.ceil(downloadsData.total / downloadsData.page_size))

  return (
    <div className="page-stack">
      <section className="panel">
        <div className="panel-header">
          <div>
            <h3>Download diagnostics</h3>
            <p className="panel-subtitle">Validate a URL without sending media to Telegram</p>
          </div>
        </div>

        <form className="form-grid" onSubmit={runTest}>
          <input
            className="input"
            placeholder="Paste TikTok or YouTube URL"
            value={testUrl}
            onChange={event => setTestUrl(event.target.value)}
          />
          <button className="button" type="submit">Run test</button>
        </form>

        {testResult ? (
          <div className="list-row" style={{ marginTop: 14 }}>
            <div>
              <strong>{testResult.title || 'Untitled media'}</strong>
              <span className="muted">
                {testResult.platform} / {testResult.media_type || 'unknown'}
              </span>
            </div>
            <span className={`badge ${testResult.success ? 'success' : 'failed'}`}>
              {testResult.success ? 'Ready' : testResult.error}
            </span>
          </div>
        ) : null}
      </section>

      <section className="panel">
        <div className="panel-header">
          <div>
            <h3>Download history</h3>
            <p className="panel-subtitle">Success, failures and metadata for recent requests</p>
          </div>
          <button className="button-secondary" onClick={() => fetchDownloads(page, filters)}>Refresh</button>
        </div>

        <div className="filter-bar">
          <input
            className="input"
            placeholder="Search URL, title or Telegram ID"
            value={filters.search}
            onChange={event => setFilters(current => ({ ...current, search: event.target.value }))}
          />
          <select
            className="select"
            value={filters.platform}
            onChange={event => setFilters(current => ({ ...current, platform: event.target.value }))}
          >
            <option value="">All platforms</option>
            <option value="tiktok">TikTok</option>
            <option value="youtube">YouTube</option>
          </select>
          <select
            className="select"
            value={filters.status}
            onChange={event => setFilters(current => ({ ...current, status: event.target.value }))}
          >
            <option value="">All statuses</option>
            <option value="success">Success</option>
            <option value="failed">Failed</option>
            <option value="processing">Processing</option>
          </select>
          <button
            className="button"
            onClick={() => {
              setPage(1)
              fetchDownloads(1, filters)
            }}
          >
            Apply
          </button>
          <button
            className="button-secondary"
            onClick={() => {
              setFilters(DEFAULT_FILTERS)
              setPage(1)
              fetchDownloads(1, DEFAULT_FILTERS)
            }}
          >
            Reset
          </button>
        </div>

        {error ? <div className="error-state">{error}</div> : null}
        {loading ? <div className="empty-state">Loading activity...</div> : null}

        {!loading && (
          <>
            <div className="table-wrap">
              <table className="table">
                <thead>
                  <tr>
                    <th>When</th>
                    <th>User</th>
                    <th>Platform</th>
                    <th>Status</th>
                    <th>Title</th>
                    <th>Files</th>
                    <th>URL</th>
                  </tr>
                </thead>
                <tbody>
                  {downloadsData.items.map(item => (
                    <tr key={item.id}>
                      <td>{new Date(item.created_at).toLocaleString()}</td>
                      <td>{item.telegram_id || 'Unknown'}</td>
                      <td>
                        <span className="badge neutral">{item.platform}</span>
                      </td>
                      <td>
                        <span className={`badge ${item.status}`}>{item.status}</span>
                        {item.error_message ? <div className="muted">{item.error_message}</div> : null}
                      </td>
                      <td>{item.title || 'Untitled'}</td>
                      <td>
                        {item.file_count} file(s)
                        <div className="muted">{item.file_size_bytes} bytes</div>
                      </td>
                      <td className="muted" style={{ maxWidth: 280, wordBreak: 'break-word' }}>{item.url}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="pagination">
              <span className="muted">
                Page {page} of {totalPages} with {downloadsData.total} events
              </span>
              <div className="inline-actions">
                <button
                  className="button-secondary"
                  disabled={page <= 1}
                  onClick={() => {
                    const nextPage = page - 1
                    setPage(nextPage)
                    fetchDownloads(nextPage, filters)
                  }}
                >
                  Previous
                </button>
                <button
                  className="button-secondary"
                  disabled={page >= totalPages}
                  onClick={() => {
                    const nextPage = page + 1
                    setPage(nextPage)
                    fetchDownloads(nextPage, filters)
                  }}
                >
                  Next
                </button>
              </div>
            </div>
          </>
        )}
      </section>
    </div>
  )
}
