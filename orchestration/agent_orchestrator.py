"""Wires the agent fleet onto a shared EventBus and runs trading cycles."""
from __future__ import annotations

from agents.data_agent import DataAgent
from agents.momentum_agent import MomentumAgent
from agents.sentiment_agent import SentimentAgent
from agents.risk_agent import RiskAgent
from agents.execution_agent import ExecutionAgent
from agents.supervisor_agent import SupervisorAgent
from orchestration.event_bus import EventBus, Topic
from trading_engine.execution.execution_gateway import RiskManager, PaperExecutor


class AgentOrchestrator:
    """Builds the full data -> strategy -> risk -> execution pipeline.

    The market/risk state lives in an injected FeatureStoreEngine, so the same
    orchestrator drives both tests (seeded in-memory engine) and production
    (live engine)."""

    def __init__(self, engine, portfolio_model=None, symbol: str = "BTC-USD",
                 db_path: str = "paper_ledger.sqlite", sentiment_processor=None) -> None:
        self.bus = EventBus()
        self.engine = engine

        risk_manager = RiskManager(engine, portfolio_model=portfolio_model)
        executor = PaperExecutor(risk_manager, engine, db_path=db_path)

        self.data_agent = DataAgent(self.bus)
        self.momentum_agent = MomentumAgent(self.bus, symbol=symbol)
        self.sentiment_agent = SentimentAgent(self.bus, processor=sentiment_processor, symbol=symbol)
        self.risk_agent = RiskAgent(self.bus, risk_manager)
        self.execution_agent = ExecutionAgent(self.bus, executor)
        self.supervisor = SupervisorAgent(self.bus, fleet=[
            self.data_agent, self.momentum_agent, self.sentiment_agent,
            self.risk_agent, self.execution_agent,
        ])

    def run_cycle(self, frame):
        """Inject one market-data frame and let it propagate through the fleet.
        Returns every event produced during the cycle."""
        start = len(self.bus.log)
        self.data_agent.emit_market_data(frame)
        return self.bus.log[start:]

    def fills(self):
        return self.bus.events(Topic.ORDER_FILLED)

    def health(self) -> dict:
        return self.supervisor.fleet_health()


__all__ = ["AgentOrchestrator"]
