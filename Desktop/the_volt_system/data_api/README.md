# data_api

Local FastAPI service to collect and export market + macro + news datasets for model training.

## Setup (Windows)

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r data_api/requirements.txt
```

## Run API

```powershell
.\.venv\Scripts\python.exe -m uvicorn data_api.app:app --host 127.0.0.1 --port 8000 --reload
```

## Run one-off collection

```powershell
.\.venv\Scripts\python.exe -m data_api.jobs.run_once
```

## Run production pipeline (notebook-free)

```powershell
.\.venv\Scripts\python.exe -m data_api.jobs.run_production
```

Optional Kaggle export in the same run:

```powershell
.\.venv\Scripts\python.exe -m data_api.jobs.run_production --prepare-kaggle
```

## Run retention and archival maintenance

Preview retention actions:

```powershell
.\.venv\Scripts\python.exe -m data_api.jobs.data_retention --prune-archive --dry-run
```

Execute retention actions:

```powershell
.\.venv\Scripts\python.exe -m data_api.jobs.data_retention --prune-archive
```

Default schedule policy: run daily at `02:30` local time.
Detailed policy: `documentation/DATA_RETENTION_POLICY.md`.

## Phase 1 BrowserCollector (optional)

Browser collection is feature-flagged and disabled by default.

Enable it with environment variables:

```powershell
$env:DATA_API_BROWSER_ENABLED = "true"
$env:DATA_API_BROWSER_HEADLESS = "true"
$env:DATA_API_BROWSER_TIMEOUT_MS = "30000"
```

Optional target override format:

```powershell
$env:DATA_API_BROWSER_TARGETS = "tradingview=https://www.tradingview.com/markets/cryptocurrencies/prices-all/,investing=https://www.investing.com/crypto/"
```

Install browser runtime once after dependency install:

```powershell
.\.venv\Scripts\python.exe -m playwright install chromium
```

## Prepare Kaggle-ready CSV

```powershell
.\.venv\Scripts\python.exe -m data_api.jobs.prepare_kaggle_dataset
```

This creates a stable upload file at:
- `data_api/data/kaggle/volt_training_dataset.csv`

## Endpoints

- `GET /health`
- `POST /collect/market`
- `POST /collect/news`
- `POST /collect/browser`
- `POST /collect/reddit`
- `POST /collect/macro`
- `POST /collect/desktop`
- `POST /collect/full`
- `POST /stream/finance-query/config`
- `GET /datasets/latest`

## Additional source flags

Reddit API:

```powershell
$env:DATA_API_REDDIT_ENABLED = "true"
$env:DATA_API_REDDIT_CLIENT_ID = "<client-id>"
$env:DATA_API_REDDIT_CLIENT_SECRET = "<client-secret>"
$env:DATA_API_REDDIT_USER_AGENT = "volt-data-api/1.0"
$env:DATA_API_REDDIT_SUBREDDITS = "cryptocurrency,bitcoin,ethtrader"
```

FRED macro series:

```powershell
$env:DATA_API_MACRO_ENABLED = "true"
$env:DATA_API_FRED_API_KEY = "<fred-api-key>"
$env:DATA_API_FRED_SERIES = "fed_funds_rate=FEDFUNDS,cpi_all_items=CPIAUCSL,real_gdp=GDPC1"
```

Desktop capture (+ optional vision hook):

```powershell
$env:DATA_API_DESKTOP_ENABLED = "true"
$env:DATA_API_DESKTOP_TARGETS = "trading_terminal=active_screen"
$env:DATA_API_VISION_ENABLED = "true"
```

Yahoo primary + FCS fallback for forex/crypto:

```powershell
$env:DATA_API_FCS_API_KEY = "<fcs-api-key>"
```

TokenInsight crypto news sentiment:

```powershell
$env:DATA_API_TOKENINSIGHT_ENABLED = "true"
$env:DATA_API_TOKENINSIGHT_API_KEY = "<tokeninsight-api-key>"
```

Optional Finance Query websocket stream config:

```powershell
$env:DATA_API_FINANCE_QUERY_STREAM_ENABLED = "true"
$env:DATA_API_FINANCE_QUERY_WS_URL = "wss://stream.financequery.com/ws"
$env:DATA_API_FINANCE_QUERY_CHANNELS = "ticker,trades,orderbook"
```

All generated files are stored under `data_api/data/`.
Default storage format is CSV.

Notebooks are for exploration and reporting; production data runs should use module entrypoints above.
