from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

import pandas as pd
import logging

from data_api.exceptions import FileStoreError, ValidationError

logger = logging.getLogger(__name__)


class FileStore:
    """Store files in CSV and Parquet formats.
    
    Automatically falls back to CSV if Parquet is enabled but fails.
    """
    
    def __init__(self, base_dir: Path) -> None:
        self.base_dir = base_dir
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _build_unique_path(self, prefix: str, extension: str) -> Path:
        """Build a unique output path for fast consecutive writes."""
        # Include microseconds to avoid same-second collisions.
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S_%f")
        candidate = self.base_dir / f"{prefix}_{timestamp}.{extension}"
        if not candidate.exists():
            return candidate

        # Rare fallback if a collision still happens.
        suffix = 1
        while True:
            fallback = self.base_dir / f"{prefix}_{timestamp}_{suffix}.{extension}"
            if not fallback.exists():
                return fallback
            suffix += 1

    def save(self, df: pd.DataFrame, prefix: str, reject_empty: bool = False) -> Path:
        """Save DataFrame to CSV or Parquet file.
        
        Args:
            df: DataFrame to save.
            prefix: Filename prefix (e.g., 'market', 'news').
        
        Returns:
            Path to saved file.
        
        Raises:
            ValidationError: If DataFrame is None.
            FileStoreError: If both CSV and Parquet save fail.
        """
        dataset_name = prefix
        if (df is None or df.empty) and reject_empty:
            raise FileStoreError(
                "Cannot save empty or None DataFrame",
                context={"dataset": dataset_name},
            )
        if df is None:
            logger.error("Cannot save None DataFrame")
            raise ValidationError("DataFrame cannot be None")

        should_prefer_parquet = os.getenv("DATA_API_PREFER_PARQUET", "false").strip().lower() == "true"

        if should_prefer_parquet:
            parquet_path = self._build_unique_path(prefix, "parquet")
            parquet_tmp_path = Path(str(parquet_path) + ".tmp")
            try:
                df.to_parquet(parquet_tmp_path, index=False)
                if parquet_tmp_path.exists():
                    os.replace(parquet_tmp_path, parquet_path)
                return parquet_path
            except (IOError, OSError, ValueError, TypeError, ImportError) as e:
                logger.warning(f"Failed to save {prefix} as Parquet: {e}. Falling back to CSV.")
                if parquet_tmp_path.exists():
                    parquet_tmp_path.unlink(missing_ok=True)

        csv_path = self._build_unique_path(prefix, "csv")
        csv_tmp_path = Path(str(csv_path) + ".tmp")
        try:
            df.to_csv(csv_tmp_path, index=False)
            if csv_tmp_path.exists():
                os.replace(csv_tmp_path, csv_path)
            logger.info(f"Saved {prefix} to {csv_path}")
            return csv_path
        except (IOError, OSError) as e:
            if csv_tmp_path.exists():
                csv_tmp_path.unlink(missing_ok=True)
            logger.error(f"Failed to save {prefix} as CSV: {e}")
            raise FileStoreError(f"Failed to save file: {e}")

    def latest_file(self, prefix: str) -> Path | None:
        """Find the most recent file matching the prefix.
        
        Args:
            prefix: Filename prefix to search for.
        
        Returns:
            Path to most recent file, or None if no matches found.
        """
        candidates = sorted(self.base_dir.glob(f"{prefix}_*"), key=lambda p: p.stat().st_mtime, reverse=True)
        return candidates[0] if candidates else None
