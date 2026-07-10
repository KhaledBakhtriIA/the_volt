from __future__ import annotations

import logging
from pathlib import Path
from typing import List

logger = logging.getLogger(__name__)


class VisionExtractor:
    """Best-effort screenshot extraction layer for desktop collector outputs.

    This class intentionally keeps a no-fail interface so desktop collection
    remains non-blocking when a vision model runtime is unavailable.
    """

    def __init__(self, enabled: bool = False) -> None:
        self.enabled = enabled

    def extract_rows(self, image_path: Path, prompt: str) -> List[dict]:
        """Extract structured rows from screenshot.

        Returns an empty list when disabled or when no model runtime is configured.
        """
        if not self.enabled:
            return []

        # Placeholder hook: integrate a real vision-model client here.
        logger.info("Vision extraction enabled but no backend configured for %s", image_path)
        return []
