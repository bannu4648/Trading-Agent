import { useNavigate } from 'react-router-dom';
import hkuLogo from '../assets/hku-logo.png';

export default function LaunchPage() {
    const navigate = useNavigate();

    const handleRunSp500 = () => {
        navigate('/run/developer?mode=sp500&quickrun=1');
    };

    return (
        <div>
            <div className="card landing-title-card" style={{ marginBottom: 'var(--sp-lg)' }}>
                <img src={hkuLogo} alt="HKU logo" className="landing-title-logo" />
                <h2 className="landing-title-main">
                    Multi Agent AI System for Stock Analysis, Trading and Portfolio Management
                </h2>
                <p className="landing-title-sub">
                    This project is our final-year capstone for the MSc in Financial Technology and Data Analytics.
                </p>
            </div>

            <div className="landing-hero card" style={{ marginBottom: 'var(--sp-lg)' }}>
                <div className="landing-hero-content">
                    <p className="landing-kicker">Research-to-portfolio workflow</p>
                    <p className="landing-subtitle">
                        The platform combines technical analysis, sentiment intelligence, and fundamentals into one
                        consistent decision workflow, followed by allocation and risk validation.
                    </p>
                    <div className="landing-highlight-pill">One integrated pipeline from screening to risk checks</div>
                    <div className="landing-chip-row">
                        <span className="landing-chip">Technical</span>
                        <span className="landing-chip">Sentiment</span>
                        <span className="landing-chip">Fundamentals</span>
                        <span className="landing-chip">Risk Validation</span>
                    </div>
                    <div className="landing-action-row">
                        <button type="button" className="btn btn-primary" onClick={handleRunSp500}>
                            Run (S&P500 Screened)
                        </button>
                        <a
                            href="https://github.com/bannu4648/Trading-Agent.git"
                            target="_blank"
                            rel="noreferrer"
                            className="btn btn-github"
                        >
                            <span className="github-icon" aria-hidden="true">
                                <svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor">
                                    <path d="M12 .5a12 12 0 0 0-3.79 23.39c.6.11.82-.26.82-.58v-2.02c-3.34.73-4.04-1.42-4.04-1.42-.55-1.37-1.33-1.74-1.33-1.74-1.08-.74.08-.72.08-.72 1.2.08 1.83 1.22 1.83 1.22 1.06 1.8 2.8 1.28 3.48.98.11-.76.42-1.28.76-1.57-2.67-.3-5.47-1.31-5.47-5.85 0-1.29.47-2.35 1.22-3.18-.12-.3-.53-1.53.12-3.19 0 0 1-.31 3.3 1.21a11.5 11.5 0 0 1 6 0c2.3-1.52 3.3-1.21 3.3-1.21.65 1.66.24 2.89.12 3.19.76.83 1.22 1.89 1.22 3.18 0 4.55-2.81 5.55-5.49 5.84.43.37.82 1.09.82 2.2v3.26c0 .32.22.69.83.58A12 12 0 0 0 12 .5Z" />
                                </svg>
                            </span>
                            View GitHub
                        </a>
                    </div>
                </div>
                <div className="landing-hero-metrics">
                    <div className="landing-metric-card">
                        <span className="landing-metric-label">Default Universe</span>
                        <span className="landing-metric-value">S&P 500</span>
                        <span className="landing-metric-sub">Best first run for full workflow</span>
                    </div>
                    <div className="landing-metric-card">
                        <span className="landing-metric-label">Pipeline Stages</span>
                        <span className="landing-metric-value">5</span>
                        <span className="landing-metric-sub">From screening to validation</span>
                    </div>
                    <div className="landing-metric-card">
                        <span className="landing-metric-label">Output</span>
                        <span className="landing-metric-value">Risk-checked portfolio</span>
                        <span className="landing-metric-sub">With per-ticker explanation</span>
                    </div>
                </div>
            </div>

            <div className="landing-grid">
                <div className="card">
                    <div className="card-header">
                        <h3>How it works</h3>
                    </div>
                    <ol className="landing-steps">
                        <li>
                            <strong>Screen the universe</strong>
                            <span>Start broad, then narrow to candidates with strong expected signal quality.</span>
                        </li>
                        <li>
                            <strong>Run multi-agent analysis</strong>
                            <span>Evaluate technicals, sentiment, and fundamentals with transparent per-ticker outputs.</span>
                        </li>
                        <li>
                            <strong>Validate portfolio risk</strong>
                            <span>Review sizing, risk controls, and rebalance impact before final action.</span>
                        </li>
                    </ol>
                </div>

                <div className="card">
                    <div className="card-header">
                        <h3>Benefits of using this application</h3>
                    </div>
                    <div className="landing-mode-list">
                        <div className="landing-mode-item">
                            <span className="landing-mode-title">Explainable outputs</span>
                            <span className="landing-mode-desc">
                                Recommendations are backed by traceable evidence from each analysis stage.
                            </span>
                        </div>
                        <div className="landing-mode-item">
                            <span className="landing-mode-title">Efficient workflow</span>
                            <span className="landing-mode-desc">
                                Research, allocation, and risk are reviewed in one interface without tool switching.
                            </span>
                        </div>
                        <div className="landing-mode-item">
                            <span className="landing-mode-title">Safer experimentation</span>
                            <span className="landing-mode-desc">
                                Paper execution and risk checks support controlled iteration before deployment.
                            </span>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
}
