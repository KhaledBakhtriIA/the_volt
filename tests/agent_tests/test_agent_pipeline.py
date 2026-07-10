import pandas as pd
import pytest

from data_layer.feature_store.feature_store_engine import FeatureStoreEngine, FeatureStoreConfig
from trading_engine.risk_management.risk_management import PortfolioRiskModel
from orchestration.agent_orchestrator import AgentOrchestrator
from orchestration.event_bus import Topic
from orchestration.workflow_manager import WorkflowManager


@pytest.fixture
def seeded_engine():
    """FeatureStoreEngine pre-seeded with BTC-USD ticks for risk + execution."""
    config = FeatureStoreConfig(
        required_columns=["symbol", "timestamp", "price"],
        numeric_columns=["price"],
        persist_offline=False,
    )
    engine = FeatureStoreEngine(config)
    df = pd.DataFrame({
        "symbol": ["BTC-USD", "BTC-USD"],
        "timestamp": ["2026-03-30T10:00:00Z", "2026-03-30T10:01:00Z"],
        "price": [60000.0, 60100.0],
    })
    engine.process(df, dataset="realtime_ticks", strict=False)
    return engine


def _funded_portfolio(equity=1_000_000.0):
    p = PortfolioRiskModel()
    p.sync_equity(equity)
    return p


def _rising_frame():
    return pd.DataFrame({"symbol": ["BTC-USD", "BTC-USD"], "price": [60000.0, 60600.0]})


def test_full_agent_pipeline_fills_order(seeded_engine, tmp_path):
    orch = AgentOrchestrator(
        seeded_engine, portfolio_model=_funded_portfolio(),
        db_path=str(tmp_path / "ledger.sqlite"),
    )

    events = orch.run_cycle(_rising_frame())
    topics = [e.topic for e in events]

    # data -> signal -> sized order -> fill all propagate in one cycle
    assert Topic.MARKET_DATA in topics
    assert Topic.SIGNAL in topics
    assert Topic.SIZED_ORDER in topics
    fills = orch.fills()
    assert len(fills) == 1
    assert fills[0].payload["order"].fill_price > 59000.0


def test_pipeline_vetoes_when_kill_switch_active(seeded_engine, tmp_path):
    # PortfolioRiskModel with no equity synced -> kill switch halts sizing
    orch = AgentOrchestrator(
        seeded_engine, portfolio_model=PortfolioRiskModel(),
        db_path=str(tmp_path / "ledger.sqlite"),
    )

    orch.run_cycle(_rising_frame())

    assert orch.fills() == []
    assert len(orch.bus.events(Topic.ORDER_REJECTED)) >= 1


def test_supervisor_reports_healthy_fleet(seeded_engine, tmp_path):
    orch = AgentOrchestrator(
        seeded_engine, portfolio_model=_funded_portfolio(),
        db_path=str(tmp_path / "ledger.sqlite"),
    )
    orch.run_cycle(_rising_frame())

    health = orch.health()
    assert health["status"] == "ok"
    assert health["agents"] == 5
    assert health["events_on_bus"] > 0


def test_workflow_manager_runs_named_cycle(seeded_engine, tmp_path):
    orch = AgentOrchestrator(
        seeded_engine, portfolio_model=_funded_portfolio(),
        db_path=str(tmp_path / "ledger.sqlite"),
    )
    wf = WorkflowManager()
    wf.register("trade_cycle", [
        ("ingest_and_trade", lambda: len(orch.run_cycle(_rising_frame()))),
        ("check_fills", lambda: len(orch.fills())),
    ])

    results = wf.run("trade_cycle")

    assert [r.name for r in results] == ["ingest_and_trade", "check_fills"]
    assert all(r.ok for r in results)
