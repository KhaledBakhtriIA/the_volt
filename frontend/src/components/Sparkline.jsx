// Single-series equity sparkline. One series => no legend; the card title names
// it. 2px line, soft area fill, an >=8px marker anchored to the latest point.
export default function Sparkline({ data, width = 640, height = 150, up = true }) {
  if (!data || data.length < 2) return null

  const pad = 6
  const min = Math.min(...data)
  const max = Math.max(...data)
  const span = max - min || 1
  const dx = (width - pad * 2) / (data.length - 1)

  const x = (i) => pad + i * dx
  const y = (v) => pad + (height - pad * 2) * (1 - (v - min) / span)

  const line = data.map((v, i) => `${i === 0 ? 'M' : 'L'} ${x(i).toFixed(1)} ${y(v).toFixed(1)}`).join(' ')
  const area = `${line} L ${x(data.length - 1).toFixed(1)} ${height - pad} L ${x(0).toFixed(1)} ${height - pad} Z`

  const stroke = up ? 'var(--aqua)' : 'var(--critical)'
  const lastX = x(data.length - 1)
  const lastY = y(data[data.length - 1])

  return (
    <svg width="100%" viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none"
         role="img" aria-label="Simulated paper-trading equity curve" style={{ display: 'block' }}>
      <defs>
        <linearGradient id="eqfill" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%"  stopColor={stroke} stopOpacity="0.28" />
          <stop offset="100%" stopColor={stroke} stopOpacity="0" />
        </linearGradient>
      </defs>
      <path d={area} fill="url(#eqfill)" />
      <path d={line} fill="none" stroke={stroke} strokeWidth="2"
            strokeLinejoin="round" strokeLinecap="round" vectorEffect="non-scaling-stroke" />
      <circle cx={lastX} cy={lastY} r="4.5" fill={stroke} />
      <circle cx={lastX} cy={lastY} r="4.5" fill="none" stroke="var(--surface-1)" strokeWidth="2" />
    </svg>
  )
}
