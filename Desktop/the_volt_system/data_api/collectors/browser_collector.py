from __future__ import annotations

import logging
from typing import Dict, List

import pandas as pd

from data_api.collectors.collector_contract import ensure_collector_contract

logger = logging.getLogger(__name__)


DEFAULT_BROWSER_COLUMNS = [
    "timestamp",
    "source",
    "fetched_at_utc",
    "target_url",
    "title",
    "value",
]


class BrowserCollector:
    """Collect dynamic web data using a real browser (Playwright)."""

    def __init__(self, headless: bool = True, timeout_ms: int = 30000, max_rows_per_target: int = 50) -> None:
        self.headless = headless
        self.timeout_ms = timeout_ms
        self.max_rows_per_target = max_rows_per_target

    def _fetch_target(self, source: str, url: str, max_rows: int) -> pd.DataFrame:
        """Fetch one browser target and return a normalized DataFrame."""
        try:
            from playwright.sync_api import sync_playwright
        except Exception:
            logger.warning("Playwright is not installed; skipping browser source '%s'", source)
            return pd.DataFrame(columns=DEFAULT_BROWSER_COLUMNS)

        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(headless=self.headless)
                page = browser.new_page()
                page.goto(url, wait_until="domcontentloaded", timeout=self.timeout_ms)
                page.wait_for_timeout(500)

                rows = page.evaluate(
                    """
                    (maxRows) => {
                      const nowIso = new Date().toISOString();
                      const out = [];

                      const tableRows = Array.from(document.querySelectorAll('table tr')).slice(0, maxRows);
                      for (const row of tableRows) {
                        const text = row.innerText ? row.innerText.trim() : '';
                        if (!text) continue;
                        out.push({
                          timestamp: nowIso,
                          title: (text.split('\n')[0] || '').slice(0, 120),
                          value: text.slice(0, 600),
                          target_url: location.href,
                        });
                      }

                      if (out.length === 0) {
                        const bodyText = (document.body && document.body.innerText) ? document.body.innerText.trim() : '';
                        out.push({
                          timestamp: nowIso,
                          title: document.title || '',
                          value: bodyText.slice(0, 600),
                          target_url: location.href,
                        });
                      }

                      return out;
                    }
                    """,
                    max_rows,
                )

                browser.close()

            if not rows:
                return pd.DataFrame(columns=DEFAULT_BROWSER_COLUMNS)

            df = pd.DataFrame(rows)
            df = ensure_collector_contract(df, source=source, timestamp_col="timestamp")
            if "target_url" not in df.columns:
                df["target_url"] = url
            if "title" not in df.columns:
                df["title"] = ""
            if "value" not in df.columns:
                df["value"] = ""
            return df
        except Exception as exc:
            logger.warning("Browser collection failed for '%s' (%s): %s", source, url, exc)
            return pd.DataFrame(columns=DEFAULT_BROWSER_COLUMNS)

    def fetch(self, targets: Dict[str, str] | None = None, max_rows_per_target: int | None = None) -> pd.DataFrame:
        """Fetch one or more browser targets and return unified rows."""
        selected_targets = targets or {}
        if not selected_targets:
            return pd.DataFrame(columns=DEFAULT_BROWSER_COLUMNS)

        per_target_limit = max_rows_per_target or self.max_rows_per_target
        frames: List[pd.DataFrame] = []

        for source, url in selected_targets.items():
            target_df = self._fetch_target(source=source, url=url, max_rows=per_target_limit)
            if not target_df.empty:
                frames.append(target_df)

        if not frames:
            return pd.DataFrame(columns=DEFAULT_BROWSER_COLUMNS)

        combined = pd.concat(frames, ignore_index=True)
        combined["timestamp"] = pd.to_datetime(combined["timestamp"], utc=True, errors="coerce")
        combined = combined.dropna(subset=["timestamp"]) 
        combined = combined.sort_values(["source", "timestamp"], ascending=[True, False]).reset_index(drop=True)
        return combined
