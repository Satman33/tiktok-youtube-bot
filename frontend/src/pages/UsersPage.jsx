import { useEffect, useState } from 'react'
import axios from 'axios'

const DEFAULT_FILTERS = {
  search: '',
  banned: '',
  vip: '',
}

function buildQuery(page, filters) {
  const params = new URLSearchParams({
    page: String(page),
    page_size: '12',
  })

  if (filters.search) params.set('search', filters.search)
  if (filters.banned !== '') params.set('banned', filters.banned)
  if (filters.vip !== '') params.set('vip', filters.vip)
  return params.toString()
}

export default function UsersPage() {
  const [usersData, setUsersData] = useState({ items: [], total: 0, page: 1, page_size: 12 })
  const [filters, setFilters] = useState(DEFAULT_FILTERS)
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [limitInputs, setLimitInputs] = useState({})

  async function fetchUsers(nextPage = page, nextFilters = filters) {
    try {
      setLoading(true)
      setError('')
      const response = await axios.get(`/api/users?${buildQuery(nextPage, nextFilters)}`)
      setUsersData(response.data)
    } catch (err) {
      setError(err.response?.data?.detail || err.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchUsers(1, filters)
  }, [])

  async function handleAction(action) {
    try {
      setError('')
      await action()
      await fetchUsers(page, filters)
    } catch (err) {
      setError(err.response?.data?.detail || err.message)
    }
  }

  function applyFilters(event) {
    event.preventDefault()
    setPage(1)
    fetchUsers(1, filters)
  }

  const totalPages = Math.max(1, Math.ceil(usersData.total / usersData.page_size))

  return (
    <div className="page-stack">
      <section className="panel">
        <div className="panel-header">
          <div>
            <h3>User operations</h3>
            <p className="panel-subtitle">Search, moderate, upgrade and reset limits</p>
          </div>
          <button className="button-secondary" onClick={() => fetchUsers(page, filters)}>Refresh</button>
        </div>

        <form className="filter-bar" onSubmit={applyFilters}>
          <input
            className="input"
            placeholder="Search by Telegram ID"
            value={filters.search}
            onChange={event => setFilters(current => ({ ...current, search: event.target.value }))}
          />
          <select
            className="select"
            value={filters.banned}
            onChange={event => setFilters(current => ({ ...current, banned: event.target.value }))}
          >
            <option value="">All ban states</option>
            <option value="true">Banned</option>
            <option value="false">Active</option>
          </select>
          <select
            className="select"
            value={filters.vip}
            onChange={event => setFilters(current => ({ ...current, vip: event.target.value }))}
          >
            <option value="">All access tiers</option>
            <option value="true">VIP</option>
            <option value="false">Regular</option>
          </select>
          <button className="button" type="submit">Apply</button>
          <button
            className="button-secondary"
            type="button"
            onClick={() => {
              setFilters(DEFAULT_FILTERS)
              setPage(1)
              fetchUsers(1, DEFAULT_FILTERS)
            }}
          >
            Reset
          </button>
        </form>

        {error ? <div className="error-state">{error}</div> : null}
        {loading ? <div className="empty-state">Loading users...</div> : null}

        {!loading && (
          <>
            <div className="table-wrap">
              <table className="table">
                <thead>
                  <tr>
                    <th>Telegram ID</th>
                    <th>Status</th>
                    <th>Today</th>
                    <th>Limit</th>
                    <th>Last activity</th>
                    <th>Created</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {usersData.items.map(user => (
                    <tr key={user.id}>
                      <td>
                        <strong>{user.telegram_id}</strong>
                        <div className="muted">User #{user.id}</div>
                      </td>
                      <td>
                        <div className="inline-actions">
                          <span className={`badge ${user.is_banned ? 'banned' : 'success'}`}>
                            {user.is_banned ? 'Banned' : 'Active'}
                          </span>
                          <span className={`badge ${user.is_vip ? 'vip' : 'neutral'}`}>
                            {user.is_vip ? 'VIP' : 'Regular'}
                          </span>
                        </div>
                      </td>
                      <td>{user.today_downloads}</td>
                      <td>
                        <strong>{user.effective_daily_limit}</strong>
                        <div className="muted">
                          Override: {user.daily_limit_override ?? 'default'}
                        </div>
                      </td>
                      <td>{user.last_download_at ? new Date(user.last_download_at).toLocaleString() : 'No activity'}</td>
                      <td>{new Date(user.created_at).toLocaleString()}</td>
                      <td>
                        <div className="table-actions">
                          <button
                            className={user.is_banned ? 'button-secondary' : 'button-danger'}
                            onClick={() =>
                              handleAction(() =>
                                axios.post(`/api/${user.is_banned ? 'unban' : 'ban'}/${user.telegram_id}`)
                              )
                            }
                          >
                            {user.is_banned ? 'Unban' : 'Ban'}
                          </button>
                          <button
                            className="button-secondary"
                            onClick={() =>
                              handleAction(() =>
                                axios.post(`/api/users/${user.telegram_id}/vip`, {
                                  is_vip: !user.is_vip,
                                })
                              )
                            }
                          >
                            {user.is_vip ? 'Remove VIP' : 'Make VIP'}
                          </button>
                          <button
                            className="button-secondary"
                            onClick={() =>
                              handleAction(() => axios.post(`/api/users/${user.telegram_id}/reset-usage`))
                            }
                          >
                            Reset usage
                          </button>
                          <input
                            className="input"
                            style={{ maxWidth: 110 }}
                            placeholder="New limit"
                            value={limitInputs[user.telegram_id] ?? ''}
                            onChange={event =>
                              setLimitInputs(current => ({
                                ...current,
                                [user.telegram_id]: event.target.value,
                              }))
                            }
                          />
                          <button
                            className="button-secondary"
                            onClick={() =>
                              handleAction(() =>
                                axios.post(`/api/users/${user.telegram_id}/limit`, {
                                  daily_limit_override: limitInputs[user.telegram_id]
                                    ? Number(limitInputs[user.telegram_id])
                                    : null,
                                })
                              )
                            }
                          >
                            Save limit
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {usersData.items.length === 0 ? (
              <div className="empty-state">No users match the current filters.</div>
            ) : null}

            <div className="pagination">
              <span className="muted">
                Showing page {page} of {totalPages} with {usersData.total} users
              </span>
              <div className="inline-actions">
                <button
                  className="button-secondary"
                  disabled={page <= 1}
                  onClick={() => {
                    const nextPage = page - 1
                    setPage(nextPage)
                    fetchUsers(nextPage, filters)
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
                    fetchUsers(nextPage, filters)
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
