import { BrowserRouter, Routes, Route, NavLink, useLocation } from 'react-router-dom'
import { AnalysisSessionProvider } from './context/AnalysisSessionContext'
import AnalysisPage from './pages/AnalysisPage'
import LaunchPage from './pages/LaunchPage'
import HistoryPage from './pages/HistoryPage'
import LongShortPage from './pages/LongShortPage'
import PerformancePage from './pages/PerformancePage'
import hkuLogo from './assets/hku-logo.png'
import './index.css'

function AppContent() {
  const location = useLocation()
  const params = new URLSearchParams(location.search)
  const activeMode = params.get('mode')
  const modeActiveClass = (mode) =>
    location.pathname === '/run/developer' && activeMode === mode ? 'active' : ''

  return (
      <div className="app-layout">
        {/* ── Sidebar ── */}
        <aside className="sidebar">
          <div className="sidebar-brand">
            <img src={hkuLogo} alt="HKU logo" className="sidebar-brand-logo" />
            <h1>Multi Agent Trading System</h1>
            <p>Stock Analysis, Trading and Portfolio Management using AI Agents.</p>
          </div>

          <ul className="sidebar-nav">
            <li className="sidebar-section-title">Run Pipeline</li>
            <li>
              <NavLink to="/" end className={({ isActive }) => isActive ? 'active' : ''}>
                <span className="nav-icon">📊</span>
                Launch
              </NavLink>
            </li>
            <li className="sidebar-section-title">Pipeline Flows</li>
            <li>
              <NavLink to="/run/developer?mode=custom" className={() => modeActiveClass('custom')}>
                <span className="nav-icon">✏️</span>
                Custom Ticker
              </NavLink>
            </li>
            <li>
              <NavLink to="/run/developer?mode=top20" className={() => modeActiveClass('top20')}>
                <span className="nav-icon">⚖️</span>
                Top 20 Long/Short
              </NavLink>
            </li>
            <li>
              <NavLink to="/run/developer?mode=sp500" className={() => modeActiveClass('sp500')}>
                <span className="nav-icon">📈</span>
                S&amp;P500 Screened
              </NavLink>
            </li>
            <li className="sidebar-section-title">Results</li>
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
            <p>Multi Agent AI System for Stock Analysis, Trading and Portfolio Management | HKU MSc FTDA | FITE7001 | Group 22 | 2026</p>
          </div>
        </aside>

        {/* ── Main Content ── */}
        <main className="main-content">
          <Routes>
            <Route path="/" element={<LaunchPage />} />
            <Route path="/run/developer" element={<AnalysisPage />} />
            <Route path="/history" element={<HistoryPage />} />
            <Route path="/longshort" element={<LongShortPage />} />
            <Route path="/performance" element={<PerformancePage />} />
          </Routes>
        </main>
      </div>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <AnalysisSessionProvider>
      <AppContent />
      </AnalysisSessionProvider>
    </BrowserRouter>
  )
}
