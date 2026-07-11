// ============================================================
//  System metrics + simulated live feed.
//
//  The KPI values below are the REAL, audited numbers for the
//  Volt System repository. The trading / collector telemetry is
//  a client-side SIMULATION so the control plane can be demoed
//  without the FastAPI + Redpanda cluster running. Swap the
//  `useSimulation` hook for calls to /api/* to wire it live.
// ============================================================

// --- Real repository metrics (audited) ---
export const KPIS = [
  { label: 'Production Python', value: '8,314', sub: 'LOC · 61 modules' },
  { label: 'Test Suite', value: '190', sub: '<b>100% passing</b> · 37 files' },
  { label: 'Data Collectors', value: '11', sub: 'market · macro · social · vision' },
  { label: 'Pipeline Modules', value: '22', sub: 'src/canonical' },
  { label: 'Feature Indicators', value: '150+', sub: 'notebook-verified' },
  { label: 'Documentation', value: '17', sub: 'architecture & policy docs' },
]

// --- Data collectors (names are real; latency/status simulated) ---
export const COLLECTORS = [
  'market_collector', 'stock_market_collector', 'macro_collector',
  'news_collector', 'reddit_collector', 'trading_strategy_collector',
  'trading_mistakes_collector', 'finance_query_stream', 'browser_collector',
  'desktop_collector', 'vision_extractor',
]

const STARTING_EQUITY = 1_000_000
const KILL_SWITCH_DD = 0.20 // PortfolioRiskModel.max_global_drawdown

// Deterministic-ish random walk seed so the demo feels stable but alive.
function seededNoise() {
  return (Math.random() - 0.48)
}

// Build an initial equity curve (last ~90 ticks) with mild upward drift.
export function seedEquityCurve(n = 90) {
  const pts = []
  let eq = STARTING_EQUITY * 0.94
  for (let i = 0; i < n; i++) {
    eq = eq * (1 + (Math.random() - 0.47) * 0.006)
    pts.push(eq)
  }
  return pts
}

// Advance one tick of the simulation given previous state.
export function nextTick(prev) {
  const last = prev.curve[prev.curve.length - 1]
  const next = Math.max(last * (1 + seededNoise() * 0.004), STARTING_EQUITY * 0.6)
  const curve = [...prev.curve.slice(-119), next]

  const peak = Math.max(...curve)
  const drawdown = (peak - next) / peak

  const dayOpen = curve[Math.max(0, curve.length - 24)]
  const dailyPnl = next - dayOpen

  return {
    curve,
    equity: next,
    peak,
    drawdown,
    dailyPnl,
    dailyPnlPct: dailyPnl / dayOpen,
    killSwitch: drawdown >= KILL_SWITCH_DD,
    openPositions: prev.openPositions,
  }
}

export function seedState() {
  const curve = seedEquityCurve()
  const equity = curve[curve.length - 1]
  const peak = Math.max(...curve)
  const dayOpen = curve[Math.max(0, curve.length - 24)]
  return {
    curve,
    equity,
    peak,
    drawdown: (peak - equity) / peak,
    dailyPnl: equity - dayOpen,
    dailyPnlPct: (equity - dayOpen) / dayOpen,
    killSwitch: false,
    openPositions: 7,
  }
}

export const KILL_SWITCH_LIMIT = KILL_SWITCH_DD

// Collector status/latency snapshot (simulated).
export function sampleCollectors() {
  return COLLECTORS.map((name, i) => {
    const roll = Math.random()
    // vision/desktop are the flaky OS-automation ones — occasionally warn.
    const flaky = name === 'vision_extractor' || name === 'desktop_collector'
    let status = 'good'
    if (flaky && roll > 0.65) status = 'warning'
    const base = flaky ? 180 : 40
    const latency = Math.round(base + Math.random() * (flaky ? 240 : 90))
    return { name, status, latency }
  })
}

export const GOVERNANCE = {
  activeModel: 'xgb_clf · v14',
  challenger: 'v15 (PENDING)',
  ksStat: 0.061,
  psiStat: 0.083,
  ksThreshold: 0.15,
  psiThreshold: 0.20,
}

// --- STATIC: audited repository facts (change only with a re-audit) ---
export const STATIC_AUDIT = {
  auditedOn: '2026-07-11',
  tests: 190,
  reliability: '100%',
  reliabilityRuns: 2,
  reliabilityTrend: 'STABLE',
  loc: '8,200+',
  modules: 57,
  agents: 6,
  ci: 'GitHub Actions',
  registry: 'GHCR',
}

// --- REAL: live backend probes through the Vite proxy (/api -> FastAPI :8000) ---

// GET /api/health — returns { live, latency, service } or { live: false }.
export async function fetchBackendHealth(timeoutMs = 2500) {
  const ctrl = new AbortController()
  const timer = setTimeout(() => ctrl.abort(), timeoutMs)
  const started = performance.now()
  try {
    const res = await fetch('/api/health', { signal: ctrl.signal })
    if (!res.ok) return { live: false }
    const body = await res.json()
    return {
      live: body.status === 'ok',
      latency: Math.round(performance.now() - started),
      service: body.service || 'volt-data-api',
    }
  } catch {
    return { live: false }
  } finally {
    clearTimeout(timer)
  }
}

// GET /api/metrics — sums volt_http_requests_total from the Prometheus text
// exposition. Returns a number, or null when the backend is unreachable.
export async function fetchRequestCount(timeoutMs = 2500) {
  const ctrl = new AbortController()
  const timer = setTimeout(() => ctrl.abort(), timeoutMs)
  try {
    const res = await fetch('/api/metrics', { signal: ctrl.signal })
    if (!res.ok) return null
    const text = await res.text()
    let total = 0
    let seen = false
    for (const line of text.split('\n')) {
      if (line.startsWith('volt_http_requests_total{')) {
        const v = parseFloat(line.slice(line.lastIndexOf(' ') + 1))
        if (!Number.isNaN(v)) { total += v; seen = true }
      }
    }
    return seen ? Math.round(total) : null
  } catch {
    return null
  } finally {
    clearTimeout(timer)
  }
}
