import { useEffect, useState } from 'react'
import Sparkline from './components/Sparkline.jsx'
import {
  KPIS, GOVERNANCE, KILL_SWITCH_LIMIT, STATIC_AUDIT,
  seedState, nextTick, sampleCollectors,
  fetchBackendHealth, fetchRequestCount,
} from './data.js'

const usd = (n) => n.toLocaleString('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 })
const pct = (n) => `${(n * 100).toFixed(2)}%`

export default function App() {
  const [state, setState] = useState(seedState)
  const [collectors, setCollectors] = useState(sampleCollectors)
  const [backend, setBackend] = useState({ live: false })
  const [reqCount, setReqCount] = useState(null)

  // Simulated live feed: equity ticks every 1.4s, collectors resample every 4s.
  useEffect(() => {
    const t1 = setInterval(() => setState((s) => nextTick(s)), 1400)
    const t2 = setInterval(() => setCollectors(sampleCollectors()), 4000)
    return () => { clearInterval(t1); clearInterval(t2) }
  }, [])

  // REAL feed: poll the FastAPI gateway through the /api proxy every 5s.
  useEffect(() => {
    let cancelled = false
    const probe = async () => {
      const health = await fetchBackendHealth()
      if (cancelled) return
      setBackend(health)
      setReqCount(health.live ? await fetchRequestCount() : null)
    }
    probe()
    const t = setInterval(probe, 5000)
    return () => { cancelled = true; clearInterval(t) }
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
        {backend.live ? (
          <span className="pill"><span className="dot live" />API Live · {backend.latency} ms</span>
        ) : (
          <span className="pill"><span className="dot" style={{ background: 'var(--ink-muted)' }} />API Offline · demo</span>
        )}
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

      {/* ---------- system health & statistics ---------- */}
      <div className="section-label">System Health &amp; Statistics</div>
      <div className="health-grid">
        <div className="tile">
          <div className="k-label">API GATEWAY <span className={`chip ${backend.live ? 'good' : 'off'}`}>{backend.live ? 'Real · Live' : 'Offline'}</span></div>
          <div className="k-value tnum">{backend.live ? `${backend.latency} ms` : '—'}</div>
          <div className="k-sub">{backend.live ? `${backend.service} · /health` : 'start: docker compose up'}</div>
        </div>
        <div className="tile">
          <div className="k-label">REQUESTS SERVED <span className={`chip ${reqCount != null ? 'good' : 'off'}`}>{reqCount != null ? 'Real · Live' : 'Offline'}</span></div>
          <div className="k-value tnum">{reqCount != null ? reqCount.toLocaleString() : '—'}</div>
          <div className="k-sub">Prometheus /metrics counter</div>
        </div>
        <div className="tile">
          <div className="k-label">TEST SUITE <span className="chip blue">Static · Audited</span></div>
          <div className="k-value tnum">{STATIC_AUDIT.tests}</div>
          <div className="k-sub">tests · <b>100% passing</b> in CI</div>
        </div>
        <div className="tile">
          <div className="k-label">SUITE RELIABILITY <span className="chip blue">Static · Audited</span></div>
          <div className="k-value tnum">{STATIC_AUDIT.reliability}</div>
          <div className="k-sub">{STATIC_AUDIT.reliabilityTrend} · {STATIC_AUDIT.reliabilityRuns} runs (agent-data-fabric)</div>
        </div>
        <div className="tile">
          <div className="k-label">AGENT FLEET <span className="chip blue">Static · Audited</span></div>
          <div className="k-value tnum">{STATIC_AUDIT.agents}</div>
          <div className="k-sub">agents on the event bus</div>
        </div>
        <div className="tile">
          <div className="k-label">CI / CD <span className="chip blue">Static · Audited</span></div>
          <div className="k-value" style={{ fontSize: 22 }}>Green</div>
          <div className="k-sub">{STATIC_AUDIT.ci} → {STATIC_AUDIT.registry}</div>
        </div>
      </div>

      {/* ---------- data provenance: real vs simulated vs static ---------- */}
      <div className="section-label">Data Provenance — Real vs Simulated vs Static</div>
      <div className="grid cols-3">
        <div className="card mode-card">
          <div className="mode-head">
            <h3>Real</h3>
            <span className={`chip ${backend.live ? 'good' : 'off'}`}>{backend.live ? 'Live now' : 'Offline'}</span>
          </div>
          <p className="mode-desc">Fetched from the running FastAPI gateway through the <code>/api</code> proxy. Appears automatically when the Docker stack is up.</p>
          <ul className="plist">
            <li>API health &amp; latency (top bar)</li>
            <li>Requests-served counter</li>
            <li>Grafana / Prometheus (ports 3000 / 9090)</li>
          </ul>
          <div className="mode-note">{backend.live ? 'Backend responding — these numbers are real.' : 'Run `docker compose up` to light this column up.'}</div>
        </div>
        <div className="card mode-card">
          <div className="mode-head">
            <h3>Simulated</h3>
            <span className="chip warning">Demo feed</span>
          </div>
          <p className="mode-desc">A client-side random walk generated in the browser. Illustrates what the control plane looks like under live trading — it is <b>not</b> market data.</p>
          <ul className="plist">
            <li>Equity curve, day P&amp;L, peak equity</li>
            <li>Drawdown meter &amp; kill-switch state</li>
            <li>Collector latencies &amp; status dots</li>
          </ul>
          <div className="mode-note">Never used for decisions — visual demo only.</div>
        </div>
        <div className="card mode-card">
          <div className="mode-head">
            <h3>Static</h3>
            <span className="chip blue">Audited {STATIC_AUDIT.auditedOn}</span>
          </div>
          <p className="mode-desc">Measured directly from the repository and its CI history. Changes only when the codebase is re-audited.</p>
          <ul className="plist">
            <li>Platform metric tiles (LOC, modules, collectors)</li>
            <li>Test count &amp; reliability trend</li>
            <li>Model &amp; drift governance thresholds</li>
          </ul>
          <div className="mode-note">Source of truth: git + CI runs, not estimates.</div>
        </div>
      </div>

      <div className="foot">
        Every number on this page is labeled by provenance: <b>Real</b> (live backend), <b>Simulated</b> (browser demo feed), or <b>Static</b> (audited from the repo).
      </div>
    </div>
  )
}
