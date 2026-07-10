import { useEffect, useState } from 'react'
import Sparkline from './components/Sparkline.jsx'
import {
  KPIS, GOVERNANCE, KILL_SWITCH_LIMIT,
  seedState, nextTick, sampleCollectors,
} from './data.js'

const usd = (n) => n.toLocaleString('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 })
const pct = (n) => `${(n * 100).toFixed(2)}%`

export default function App() {
  const [state, setState] = useState(seedState)
  const [collectors, setCollectors] = useState(sampleCollectors)

  // Simulated live feed: equity ticks every 1.4s, collectors resample every 4s.
  useEffect(() => {
    const t1 = setInterval(() => setState((s) => nextTick(s)), 1400)
    const t2 = setInterval(() => setCollectors(sampleCollectors()), 4000)
    return () => { clearInterval(t1); clearInterval(t2) }
  }, [])

  const up = state.dailyPnl >= 0
  const ddPctOfLimit = Math.min(state.drawdown / KILL_SWITCH_LIMIT, 1)
  const ddColor = ddPctOfLimit > 0.75 ? 'var(--critical)' : ddPctOfLimit > 0.5 ? 'var(--warning)' : 'var(--good)'
  const healthy = collectors.filter((c) => c.status === 'good').length

  return (
    <div className="app">
      {/* ---------- top bar ---------- */}
      <header className="topbar">
        <div className="brand">
          <div className="bolt">⚡</div>
          <div>
            <h1>The Volt System</h1>
            <p>Autonomous Quant Trading · Control Plane</p>
          </div>
        </div>
        <div className="spacer" />
        <span className="pill env"><span className="dot" style={{ background: 'var(--warning)' }} />Paper</span>
        <span className="pill"><span className="dot live" />Operational</span>
      </header>

      {/* ---------- KPI tiles (real audited numbers) ---------- */}
      <div className="section-label">Platform Metrics</div>
      <div className="kpi-grid">
        {KPIS.map((k) => (
          <div className="tile" key={k.label}>
            <div className="k-label">{k.label}</div>
            <div className="k-value tnum">{k.value}</div>
            <div className="k-sub" dangerouslySetInnerHTML={{ __html: k.sub }} />
          </div>
        ))}
      </div>

      {/* ---------- live trading + risk ---------- */}
      <div className="section-label">Live Paper Trading · Simulated Feed</div>
      <div className="grid cols-2">
        <div className="card">
          <div className="card-head">
            <h2>Portfolio Equity</h2>
            <span className="hint">{state.openPositions} open positions</span>
          </div>
          <div className="equity-top">
            <div className="hero tnum">{usd(state.equity)}</div>
            <div className={`delta ${up ? 'up' : 'down'} tnum`}>
              {up ? '▲' : '▼'} {usd(Math.abs(state.dailyPnl))} ({pct(Math.abs(state.dailyPnlPct))})
            </div>
          </div>
          <Sparkline data={state.curve} up={up} />
          <div className="equity-meta">
            <div>
              <div className="m-label">PEAK EQUITY</div>
              <div className="m-val tnum">{usd(state.peak)}</div>
            </div>
            <div>
              <div className="m-label">DAY P&amp;L</div>
              <div className="m-val tnum" style={{ color: up ? 'var(--good)' : 'var(--critical)' }}>
                {up ? '+' : '−'}{usd(Math.abs(state.dailyPnl))}
              </div>
            </div>
            <div>
              <div className="m-label">SIZING</div>
              <div className="m-val">Half-Kelly</div>
            </div>
          </div>
        </div>

        <div className="card">
          <div className="card-head">
            <h2>Risk Governance</h2>
            <span className="hint">kill-switch @ {pct(KILL_SWITCH_LIMIT)}</span>
          </div>
          <div style={{ margin: '18px 0 6px' }}>
            <div className="m-label" style={{ color: 'var(--ink-muted)', fontSize: 11 }}>GLOBAL DRAWDOWN</div>
            <div className="hero tnum" style={{ fontSize: 34, color: ddColor, margin: '6px 0 14px' }}>
              {pct(state.drawdown)}
            </div>
          </div>
          <div className="meter-row">
            <div className="meter-track">
              <div className="meter-fill" style={{ width: `${ddPctOfLimit * 100}%`, background: ddColor }} />
              <div className="meter-limit" style={{ right: 0 }} />
            </div>
            <div className="meter-caption">
              <span>0%</span>
              <span>{state.killSwitch ? 'KILL-SWITCH TRIPPED' : 'within limits'}</span>
              <span>{pct(KILL_SWITCH_LIMIT)}</span>
            </div>
          </div>
          <div className="gov-row" style={{ marginTop: 18 }}>
            <span className="g-label">Portfolio kill-switch</span>
            <span className="g-val">
              <span className={`chip ${state.killSwitch ? 'warning' : 'good'}`}>
                {state.killSwitch ? 'Halted' : 'Armed'}
              </span>
            </span>
          </div>
          <div className="gov-row">
            <span className="g-label">Max position size</span>
            <span className="g-val">10% equity</span>
          </div>
          <div className="gov-row">
            <span className="g-label">Execution strategy</span>
            <span className="g-val">TWAP · sliced</span>
          </div>
        </div>
      </div>

      {/* ---------- collectors + model ---------- */}
      <div className="grid cols-2" style={{ marginTop: 16 }}>
        <div className="card">
          <div className="card-head">
            <h2>Data Ingestion</h2>
            <span className="hint">{healthy}/{collectors.length} healthy</span>
          </div>
          <div className="coll-grid">
            {collectors.map((c) => (
              <div className="coll" key={c.name}>
                <span className={`sdot ${c.status}`} />
                <span className="c-name">{c.name}</span>
                <span className="c-lat tnum">{c.latency} ms</span>
              </div>
            ))}
          </div>
        </div>

        <div className="card">
          <div className="card-head">
            <h2>Model &amp; Drift</h2>
            <span className="hint">registry · approval gate</span>
          </div>
          <div className="gov-row">
            <span className="g-label">Active model</span>
            <span className="g-val">{GOVERNANCE.activeModel} <span className="chip good">Live</span></span>
          </div>
          <div className="gov-row">
            <span className="g-label">Challenger</span>
            <span className="g-val">{GOVERNANCE.challenger} <span className="chip warning">Pending</span></span>
          </div>
          <div className="gov-row">
            <span className="g-label">Drift · KS statistic</span>
            <span className="g-val">
              <span className="bar-mini"><span style={{ width: `${(GOVERNANCE.ksStat / GOVERNANCE.ksThreshold) * 100}%`, background: 'var(--accent)' }} /></span>
              <span className="tnum">{GOVERNANCE.ksStat.toFixed(3)}</span>
            </span>
          </div>
          <div className="gov-row">
            <span className="g-label">Drift · PSI</span>
            <span className="g-val">
              <span className="bar-mini"><span style={{ width: `${(GOVERNANCE.psiStat / GOVERNANCE.psiThreshold) * 100}%`, background: 'var(--aqua)' }} /></span>
              <span className="tnum">{GOVERNANCE.psiStat.toFixed(3)}</span>
            </span>
          </div>
          <div className="gov-row">
            <span className="g-label">Retrain trigger</span>
            <span className="g-val"><span className="chip good">Idle</span></span>
          </div>
        </div>
      </div>

      <div className="foot">
        Platform metrics are audited from the repository · trading &amp; telemetry are a client-side simulation.
        Wire to the FastAPI gateway via <code>/api</code> to run live.
      </div>
    </div>
  )
}
