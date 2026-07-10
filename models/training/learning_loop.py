import asyncio
import logging
import multiprocessing
import json
import time
from pathlib import Path

import pandas as pd

from models.evaluation.drift_detector import DriftDetector
from models.registry.model_registry import ModelRegistry

logger = logging.getLogger(__name__)

def _run_training_pipeline_sync(data_dir: str, registry_db_path: str, dataset_name: str) -> None:
    '''Synchronous target for the multiprocessing background trainer.'''
    import pandas as pd
    from datetime import datetime
    
    # 1. Look for parquet files
    base_path = Path(data_dir) / dataset_name
    parquet_files = list(base_path.glob('*.parquet'))
    
    if not parquet_files:
        logging.info('No training data found. Skipping training.')
        return
        
    logging.info(f'Trainer woke up. Found {len(parquet_files)} parquet files. Starting optimization...')
    time.sleep(2) # Mocking XGBoost + Optuna compilation time to save CPU cycles for local test
    
    # 2. Mock completing training and serializing a model
    model_name = 'xgb_momentum'
    metrics = {
        'accuracy': 0.85,
        'f1': 0.82,
        'roc_auc': 0.88,
        'training_samples': len(parquet_files) * 5000 
    }
    
    # 3. Save artifact dummy
    artifact_path = Path(data_dir) / f'{model_name}_latest.pkl'
    artifact_path.write_text('MOCK_XGB_WEIGHTS', encoding='utf-8')
    
    # 4. Register in ModelRegistry
    registry = ModelRegistry(registry_db_path)
    new_version = registry.register(
        model_name=model_name,
        file_path=str(artifact_path),
        metrics_json=json.dumps(metrics)
    )
    logging.info(f'Successfully trained and registered model {model_name} version {new_version}')


class NeuroplasticityLoop:
    '''Watches FSE offline storage and triggers background retraining if thresholds are met.'''
    def __init__(
        self,
        data_dir: str = 'data_api/data/refined',
        registry_db: str = 'exports/model_registry.db',
        reference_stats_path: str | None = None,
    ):
        self.data_dir = Path(data_dir)
        self.registry_db = registry_db
        self._running = False
        self._last_file_count = 0
        self.trigger_threshold = 2
        self._last_processed_file: str = ""
        self.reference_stats_path = Path(reference_stats_path or (self.data_dir / 'reference_stats.json'))
        self.detector = DriftDetector(str(self.reference_stats_path))
    
    async def start(self) -> None:
        self._running = True
        logger.info('NeuroplasticityLoop started inspecting memories.')
        while self._running:
            await self._check_for_growth()
            await asyncio.sleep(10) # check every 10 seconds

    async def stop(self) -> None:
        self._running = False
        logger.info('NeuroplasticityLoop stopped.')

    async def _check_for_growth(self) -> None:
        base_path = self.data_dir / 'realtime_ticks'
        if not base_path.exists():
            return

        parquet_files = sorted(base_path.glob('*.parquet'))
        previous_count = self._last_file_count
        current_count = len(parquet_files)
        self._last_file_count = current_count
        if current_count == 0:
            return

        if self._last_processed_file:
            new_files = [p for p in parquet_files if p.name > self._last_processed_file]
        else:
            new_files = parquet_files

        unreadable_batches = 0
        for parquet_file in new_files:
            try:
                batch_df = pd.read_parquet(parquet_file)
            except Exception as exc:
                logger.warning('Skipping unreadable batch %s: %s', parquet_file.name, exc)
                unreadable_batches += 1
                self._last_processed_file = parquet_file.name
                continue

            if batch_df.empty:
                self._last_processed_file = parquet_file.name
                continue

            if not self.detector.has_reference:
                self.detector.save_reference(batch_df, str(self.reference_stats_path))
                logger.info('Initialized drift reference baseline from %s', parquet_file.name)
                self._last_processed_file = parquet_file.name
                continue

            drift_result = self.detector.detect(batch_df)
            drift_summary = self.detector.summary(drift_result)
            logger.info('Drift summary for %s: %s', parquet_file.name, drift_summary)

            drifted_features = [name for name, info in drift_result.items() if bool(info.get('drifted', False))]
            if len(drifted_features) >= 3:
                logger.warning(
                    'Drift trigger met with %s features (%s). Launching retraining.',
                    len(drifted_features),
                    ','.join(drifted_features),
                )
                await self._trigger_training('realtime_ticks')

            self._last_processed_file = parquet_file.name

        if unreadable_batches > 0 and (current_count - previous_count) >= self.trigger_threshold:
            logger.warning(
                'Fallback trigger activated due to %s unreadable new batches. Launching retraining.',
                unreadable_batches,
            )
            await self._trigger_training('realtime_ticks')

    async def _trigger_training(self, dataset_name: str) -> None:
        logger.info('Growth threshold met. Triggering offline trainer...')
        
        # Launching as a completely background multiprocessing job to prevent GIL blocking of StreamWorker
        process = multiprocessing.Process(
            target=_run_training_pipeline_sync,
            args=(str(self.data_dir), self.registry_db, dataset_name)
        )
        process.start()
        # Don't join(), let it detach and hit the sqlite db when it's done.
