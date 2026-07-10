# Volt Control Plane — Frontend

A small React + Vite dashboard that showcases the Volt System's metrics and a
**simulated** live paper-trading / risk / drift control plane.

- **Platform-metric tiles** (LOC, tests, collectors, modules, features, docs) are
  the real audited repository numbers, defined in [`src/data.js`](src/data.js).
- **Trading, collector telemetry, and drift** are a client-side simulation so the
  dashboard demos without the FastAPI + Redpanda cluster running.

## Run

```bash
cd frontend
npm install
npm run dev          # http://localhost:5173
```

## Build

```bash
npm run build        # -> dist/
npm run preview
```

## Wiring it to the real backend

`vite.config.js` proxies `/api/*` to the FastAPI gateway (`data_api.app`, port
8000). To go live, replace the simulation in `App.jsx`'s `useEffect` with polls to
`/api/health`, `/api/paper/pnl`, and `/api/datasets/latest`.

Design tokens are sourced from a validated (colorblind-safe) data-viz palette; see
`src/index.css`.
