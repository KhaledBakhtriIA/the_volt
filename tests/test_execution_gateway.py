import sqlite3
import pandas as pd
import pytest

from src.canonical.feature_store_engine import FeatureStoreEngine, FeatureStoreConfig
from src.canonical.execution_gateway import OrderContract, OrderSide, OrderStatus, RiskManager, PaperExecutor
from src.canonical.risk_management import PortfolioRiskModel


@pytest.fixture
def memory_engine():
    config = FeatureStoreConfig(
        required_columns=["symbol", "timestamp", "price"],
        numeric_columns=["price"],
        persist_offline=False
    )
    engine = FeatureStoreEngine(config)

    # Pre-seed FSE with fake market data
    df = pd.DataFrame({
        "symbol": ["BTC-USD", "BTC-USD"],
        "timestamp": ["2026-03-30T10:00:00Z", "2026-03-30T10:01:00Z"],
        "price": [60000.0, 60100.0]
    })
    engine.process(df, dataset="realtime_ticks", strict=False)
    return engine


def _funded_risk_manager(engine, equity=1_000_000.0):
    """Build a RiskManager whose PortfolioRiskModel has equity synced (kill-switch inactive)."""
    portfolio = PortfolioRiskModel()
    portfolio.sync_equity(equity)
    return RiskManager(engine, portfolio_model=portfolio)


def test_risk_manager_rejects_unknown_symbol(memory_engine):
    risk = _funded_risk_manager(memory_engine)

    # No market data seeded for ETH-USD -> rejected before sizing
    order = OrderContract(symbol="ETH-USD", side=OrderSide.BUY, size=1.0, strategy_id="strat_v1")
    passed, reason, size = risk.evaluate(order)
    assert not passed
    assert reason == "no_data_for_symbol"
    assert size == 0.0


def test_risk_manager_halts_when_no_equity(memory_engine):
    # PortfolioRiskModel with no equity synced -> kill switch trips inside sizing
    risk = RiskManager(memory_engine, portfolio_model=PortfolioRiskModel())

    order = OrderContract(symbol="BTC-USD", side=OrderSide.BUY, size=1.0, strategy_id="strat_v1")
    passed, reason, size = risk.evaluate(order)
    assert not passed
    assert size == 0.0


def test_risk_manager_sizes_valid_order(memory_engine):
    risk = _funded_risk_manager(memory_engine)

    order = OrderContract(symbol="BTC-USD", side=OrderSide.BUY, size=1.0, strategy_id="strat_v1")
    passed, reason, size = risk.evaluate(order)
    assert passed
    assert reason == "passed_risk_checks"
    # Clamped to the smaller of requested (1.0) vs risk-suggested size
    assert size > 0.0


def test_paper_executor_fills_order(memory_engine, tmp_path):
    risk = _funded_risk_manager(memory_engine)
    db_path = tmp_path / "test_ledger.sqlite"

    executor = PaperExecutor(risk, memory_engine, db_path=str(db_path))

    order = OrderContract(symbol="BTC-USD", side=OrderSide.BUY, size=1.0, strategy_id="strat_v1")
    result = executor.submit_order(order)

    assert result.status == OrderStatus.FILLED
    assert result.fill_price > 59000.0
    assert result.fill_timestamp is not None

    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT symbol, status, fill_price FROM paper_trades")
        rows = cursor.fetchall()
        assert len(rows) == 1
        assert rows[0][0] == "BTC-USD"
        assert rows[0][1] == "FILLED"
        assert rows[0][2] > 59000.0


def test_paper_executor_saves_rejections(memory_engine, tmp_path):
    risk = _funded_risk_manager(memory_engine)
    db_path = tmp_path / "test_ledger.sqlite"
    executor = PaperExecutor(risk, memory_engine, db_path=str(db_path))

    # Unknown symbol -> rejected and persisted with the rejection reason
    order = OrderContract(symbol="ETH-USD", side=OrderSide.BUY, size=1.0, strategy_id="bad_symbol")
    result = executor.submit_order(order)

    assert result.status == OrderStatus.REJECTED

    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT status, reason FROM paper_trades")
        rows = cursor.fetchall()
        assert rows[0] == ("REJECTED", "no_data_for_symbol")
