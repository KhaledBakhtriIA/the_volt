from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from tempfile import gettempdir
from typing import Dict, List

import pandas as pd

from data_api.collectors.collector_contract import ensure_collector_contract
from data_api.collectors.vision_extractor import VisionExtractor

logger = logging.getLogger(__name__)


class DesktopCollector:
    """Capture desktop snapshots as a last-resort data source layer."""

    def __init__(self, vision_extractor: VisionExtractor | None = None) -> None:
        self.vision_extractor = vision_extractor or VisionExtractor(enabled=False)

    def _capture(self, target_name: str) -> Path | None:
        try:
            import pyautogui  # type: ignore
            from mss import mss  # type: ignore
        except Exception:
            logger.warning("Desktop dependencies missing (pyautogui/mss); skipping '%s'", target_name)
            return None

        try:
            width, height = pyautogui.size()
            file_path = Path(gettempdir()) / f"volt_{target_name}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.png"
            with mss() as sct:
                monitor = {"top": 0, "left": 0, "width": width, "height": height}
                sct_img = sct.grab(monitor)
                from mss.tools import to_png  # type: ignore

                to_png(sct_img.rgb, sct_img.size, output=str(file_path))
            return file_path
        except Exception as exc:
            logger.warning("Desktop capture failed for '%s': %s", target_name, exc)
            return None

    def fetch(self, targets: Dict[str, str]) -> pd.DataFrame:
        """Capture desktop snapshots and emit normalized rows."""
        if not targets:
            return pd.DataFrame(columns=["timestamp", "source", "fetched_at_utc"])

        rows: List[dict] = []
        for target_name, target_hint in targets.items():
            image_path = self._capture(target_name)
            if image_path is None:
                continue

            base_row = {
                "timestamp": datetime.now(timezone.utc),
                "source": "desktop",
                "target": target_name,
                "target_hint": target_hint,
                "screenshot_path": str(image_path),
                "fetched_at_utc": datetime.now(timezone.utc).isoformat(),
            }
            rows.append(base_row)

            extracted_rows = self.vision_extractor.extract_rows(
                image_path=image_path,
                prompt="Extract key price table values and labels as JSON rows",
            )
            for extracted in extracted_rows:
                merged = base_row.copy()
                merged.update(extracted)
                rows.append(merged)

        if not rows:
            return pd.DataFrame(columns=["timestamp", "source", "fetched_at_utc"])

        result = pd.DataFrame(rows)
        result = ensure_collector_contract(result, source="desktop", timestamp_col="timestamp")
        return result.sort_values(["target", "timestamp"], ascending=[True, False]).reset_index(drop=True)
