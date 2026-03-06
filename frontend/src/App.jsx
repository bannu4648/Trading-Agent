import { useState } from 'react'
import { BrowserRouter, Routes, Route, NavLink } from 'react-router-dom'
import AnalysisPage from './pages/AnalysisPage'
import HistoryPage from './pages/HistoryPage'
import './index.css'

export default function App() {
  return (
    <BrowserRouter>
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
                New Analysis
              </NavLink>
            </li>
            <li>
              <NavLink to="/history" className={({ isActive }) => isActive ? 'active' : ''}>
                <span className="nav-icon">📁</span>
                Past Results
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
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  )
}
