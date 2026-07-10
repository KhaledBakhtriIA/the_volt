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
  { label: 'Test Suite', value: '180', sub: '<b>100% passing</b> · 34 files' },
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
