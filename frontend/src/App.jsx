import { BrowserRouter, Routes, Route, NavLink } from 'react-router-dom'
import { AnalysisSessionProvider } from './context/AnalysisSessionContext'
import AnalysisPage from './pages/AnalysisPage'
import HistoryPage from './pages/HistoryPage'
import LongShortPage from './pages/LongShortPage'
import PerformancePage from './pages/PerformancePage'
import './index.css'

export default function App() {
  return (
    <BrowserRouter>
      <AnalysisSessionProvider>
      <div className="app-layout">
        {/* ── Sidebar ── */}
        <aside className="sidebar">
          <div className="sidebar-brand">
            <h1>Trading-Agent</h1>
            <p>Multi-Agent Analysis</p>
          </div>

          <ul className="sidebar-nav">
            <li>
              <NavLink to="/" end className={({ isActive }) => isActive ? 'active' : ''}>
                <span className="nav-icon">📊</span>
                Run pipeline
              </NavLink>
            </li>
            <li>
              <NavLink to="/history" className={({ isActive }) => isActive ? 'active' : ''}>
                <span className="nav-icon">📁</span>
                Past Results
              </NavLink>
            </li>
            <li>
              <NavLink to="/performance" className={({ isActive }) => isActive ? 'active' : ''}>
                <span className="nav-icon">📉</span>
                Paper performance
              </NavLink>
            </li>
          </ul>

          <div className="sidebar-footer">
            <p>LLM Multi-Agent Financial Analysis System • HKU MSc FYP 2025</p>
          </div>
        </aside>

        {/* ── Main Content ── */}
        <main className="main-content">
          <Routes>
            <Route path="/" element={<AnalysisPage />} />
            <Route path="/history" element={<HistoryPage />} />
            <Route path="/longshort" element={<LongShortPage />} />
            <Route path="/performance" element={<PerformancePage />} />
          </Routes>
        </main>
      </div>
      </AnalysisSessionProvider>
    </BrowserRouter>
  )
}
