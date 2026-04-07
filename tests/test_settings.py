from __future__ import annotations

from dataclasses import FrozenInstanceError
import importlib

import pytest

import data_api.config.settings as settings_module
from data_api.config.settings import Settings


def test_settings_is_frozen() -> None:
    cfg = Settings()
    with pytest.raises(FrozenInstanceError):
        cfg.port = 9000


def test_settings_loads_from_environment(monkeypatch) -> None:
    monkeypatch.setenv("DATA_API_HOST", "0.0.0.0")
    monkeypatch.setenv("DATA_API_PORT", "8123")
    monkeypatch.setenv("DATA_API_INTERVAL", "1h")
    monkeypatch.setenv("DATA_API_LOOKBACK_DAYS", "14")

    importlib.reload(settings_module)
    cfg = settings_module.Settings()

    assert cfg.host == "0.0.0.0"
    assert cfg.port == 8123
    assert cfg.interval == "1h"
    assert cfg.lookback_days == 14
