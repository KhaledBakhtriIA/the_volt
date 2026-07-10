from __future__ import annotations

import shutil
from pathlib import Path

from infrastructure.config.settings import get_settings
from orchestration.jobs.pipeline import run_full_collection
from infrastructure.database.file_store import FileStore


def main() -> None:
    """Create/update a Kaggle-ready CSV dataset from latest training export."""
    settings = get_settings()
    export_store = FileStore(settings.export_dir)

    latest_export = export_store.latest_file("training_export")
    if latest_export is None:
        result = run_full_collection(settings)
        export_path = result.get("training_export_file", "")
        if not export_path:
            raise RuntimeError("No training export file available after collection run.")
        latest_export = Path(export_path)

    kaggle_dir = settings.data_root / "kaggle"
    kaggle_dir.mkdir(parents=True, exist_ok=True)
    output_path = kaggle_dir / "volt_training_dataset.csv"

    if latest_export.suffix.lower() == ".csv":
        shutil.copyfile(latest_export, output_path)
    else:
        # Safety conversion path in case parquet is enabled in the future.
        import pandas as pd

        df = pd.read_parquet(latest_export)
        df.to_csv(output_path, index=False)

    print(str(output_path))


if __name__ == "__main__":
    main()
