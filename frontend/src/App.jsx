import { useMemo, useState } from 'react'
import axios from 'axios'
import DashboardPage from './pages/DashboardPage'
import UsersPage from './pages/UsersPage'
import ActivityPage from './pages/ActivityPage'
import ErrorsPage from './pages/ErrorsPage'
import SettingsPage from './pages/SettingsPage'

const API_URL = import.meta.env.VITE_API_URL || ''

axios.defaults.baseURL = API_URL

const NAV_ITEMS = [
  { id: 'dashboard', label: 'Dashboard', hint: 'Health and KPIs' },
  { id: 'users', label: 'Users', hint: 'Moderation and limits' },
  { id: 'activity', label: 'Activity', hint: 'Downloads and test runs' },
  { id: 'errors', label: 'Errors', hint: 'Operational failures' },
  { id: 'settings', label: 'Settings', hint: 'Global controls' },
]

function App() {
  const [currentPage, setCurrentPage] = useState('dashboard')

  const CurrentPage = useMemo(() => {
    switch (currentPage) {
      case 'users':
        return UsersPage
      case 'activity':
        return ActivityPage
      case 'errors':
        return ErrorsPage
      case 'settings':
        return SettingsPage
      case 'dashboard':
      default:
        return DashboardPage
    }
  }, [currentPage])

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand-block">
          <span className="brand-badge">VD</span>
          <div>
            <p className="eyebrow">Operations Console</p>
            <h1>Video Downloader Admin</h1>
          </div>
        </div>

        <nav className="nav-list">
          {NAV_ITEMS.map(item => (
            <button
              key={item.id}
              className={`nav-item ${currentPage === item.id ? 'active' : ''}`}
              onClick={() => setCurrentPage(item.id)}
            >
              <span>{item.label}</span>
              <small>{item.hint}</small>
            </button>
          ))}
        </nav>
      </aside>

      <main className="content-area">
        <header className="topbar">
          <div>
            <p className="eyebrow">Admin panel</p>
            <h2>{NAV_ITEMS.find(item => item.id === currentPage)?.label}</h2>
          </div>
          <div className="topbar-note">Bot support, moderation and diagnostics</div>
        </header>

        <CurrentPage />
      </main>
    </div>
  )
}

export default App
