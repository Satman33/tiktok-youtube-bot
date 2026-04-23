import { useEffect, useState } from 'react'
import axios from 'axios'

const DEFAULT_FILTERS = {
  search: '',
  scope: '',
}

function buildQuery(page, filters) {
  const params = new URLSearchParams({
    page: String(page),
    page_size: '12',
  })
  if (filters.search) params.set('search', filters.search)
  if (filters.scope) params.set('scope', filters.scope)
  return params.toString()
}

export default function ErrorsPage() {
  const [errorsData, setErrorsData] = useState({ items: [], total: 0, page: 1, page_size: 12 })
  const [filters, setFilters] = useState(DEFAULT_FILTERS)
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  async function fetchErrors(nextPage = page, nextFilters = filters) {
    try {
      setLoading(true)
      setError('')
      const response = await axios.get(`/api/errors?${buildQuery(nextPage, nextFilters)}`)
      setErrorsData(response.data)
    } catch (err) {
      setError(err.response?.data?.detail || err.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchErrors(1, filters)
  }, [])

  const totalPages = Math.max(1, Math.ceil(errorsData.total / errorsData.page_size))

  return (
    <div className="page-stack">
      <section className="panel">
        <div className="panel-header">
          <div>
            <h3>Error log</h3>
            <p className="panel-subtitle">Operational failures across downloader, bot and media sending</p>
          </div>
          <button className="button-secondary" onClick={() => fetchErrors(page, filters)}>Refresh</button>
        </div>

        <div className="filter-bar">
          <input
            className="input"
            placeholder="Search message, details or Telegram ID"
            value={filters.search}
            onChange={event => setFilters(current => ({ ...current, search: event.target.value }))}
          />
          <select
            className="select"
            value={filters.scope}
            onChange={event => setFilters(current => ({ ...current, scope: event.target.value }))}
          >
            <option value="">All scopes</option>
            <option value="bot">bot</option>
            <option value="download">download</option>
            <option value="limit">limit</option>
            <option value="validation">validation</option>
            <option value="send-media">send-media</option>
            <option value="telegram-send">telegram-send</option>
          </select>
          <button
            className="button"
            onClick={() => {
              setPage(1)
              fetchErrors(1, filters)
            }}
          >
            Apply
          </button>
          <button
            className="button-secondary"
            onClick={() => {
              setFilters(DEFAULT_FILTERS)
              setPage(1)
              fetchErrors(1, DEFAULT_FILTERS)
            }}
          >
            Reset
          </button>
        </div>

        {error ? <div className="error-state">{error}</div> : null}
        {loading ? <div className="empty-state">Loading errors...</div> : null}

        {!loading && (
          <>
            <div className="table-wrap">
              <table className="table">
                <thead>
                  <tr>
                    <th>When</th>
                    <th>Scope</th>
                    <th>User</th>
                    <th>Message</th>
                    <th>Details</th>
                  </tr>
                </thead>
                <tbody>
                  {errorsData.items.map(item => (
                    <tr key={item.id}>
                      <td>{new Date(item.created_at).toLocaleString()}</td>
                      <td><span className="badge failed">{item.scope}</span></td>
                      <td>{item.telegram_id || 'Unknown'}</td>
                      <td>{item.message}</td>
                      <td className="muted" style={{ maxWidth: 320, wordBreak: 'break-word' }}>
                        {item.details || 'No details'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="pagination">
              <span className="muted">
                Page {page} of {totalPages} with {errorsData.total} entries
              </span>
              <div className="inline-actions">
                <button
                  className="button-secondary"
                  disabled={page <= 1}
                  onClick={() => {
                    const nextPage = page - 1
                    setPage(nextPage)
                    fetchErrors(nextPage, filters)
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
                    fetchErrors(nextPage, filters)
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
