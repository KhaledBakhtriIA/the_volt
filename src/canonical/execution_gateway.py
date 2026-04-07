import sqlite3
import logging
from datetime import datetime, timezone
from enum import Enum
from dataclasses import dataclass, asdict
from typing import Optional, Tuple
import pandas as pd

from src.canonical.feature_store_engine import FeatureStoreEngine

logger = logging.getLogger(__name__)

class OrderSide(Enum):
    BUY = "BUY"
    SELL = "SELL"

class OrderStatus(Enum):
    PENDING = "PENDING"
    FILLED = "FILLED"
    REJECTED = "REJECTED"

@dataclass
class OrderContract:
    symbol: str
    side: OrderSide
    size: float
    strategy_id: str
    execution_strategy: str = "MARKET"
    model_version: str = "v1"
    status: OrderStatus = OrderStatus.PENDING
    fill_price: Optional[float] = None
    fill_timestamp: Optional[str] = None
    reason: Optional[str] = None

class RiskManager:
    """Gatekeeper that enforces PortfolioRiskModel before allowing orders."""

    def __init__(self, engine: FeatureStoreEngine, portfolio_model=None):
        from src.canonical.risk_management import PortfolioRiskModel
        self.engine = engine
        self.portfolio_model = portfolio_model or PortfolioRiskModel()

    def evaluate(self, order: OrderContract, win_prob: float = 0.55, avg_win: float = 0.02, avg_loss: float = 0.01) -> Tuple[bool, str, float]:
        """
        Evaluate if order is permitted and return sized capital.
        Returns (passed, reason, suggested_size).
        """
        # Pull latest cache from the Feature Store Engine
        latest_df = self.engine.latest("realtime_ticks")
        if latest_df.empty:
            # Fallback to batch market data
            latest_df = self.engine.latest("market")
            if latest_df.empty:
                return False, "no_recent_market_data", 0.0

        # Ensure we have data for the targeted symbol
        symbol_data = latest_df[latest_df["symbol"] == order.symbol]
        if symbol_data.empty:
            return False, "no_data_for_symbol", 0.0
            
        current_price = float(symbol_data.iloc[-1]["price"])
        
        try:
            suggested_size = self.portfolio_model.calculate_position_size(
                symbol=order.symbol,
                current_price=current_price,
                win_prob=win_prob,
                avg_win=avg_win,
                avg_loss=avg_loss
            )
        except Exception as e:
            return False, str(e), 0.0
            
        if suggested_size <= 0:
            return False, "risk_model_zero_size", 0.0
            
        # If order requested a size, clamp to whichever is safer
        final_size = min(order.size, suggested_size) if order.size > 0 else suggested_size

        return True, "passed_risk_checks", final_size


class PaperExecutor:
    """Executes paper trades by resolving against the Feature Store's latest tick and maintaining a ledger."""
    
    def __init__(self, risk_manager: RiskManager, engine: FeatureStoreEngine, db_path: str = "paper_ledger.sqlite"):
        self.risk_manager = risk_manager
        self.engine = engine
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS paper_trades (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT,
                    side TEXT,
                    size REAL,
                    strategy_id TEXT,
                    model_version TEXT,
                    status TEXT,
                    fill_price REAL,
                    fill_timestamp TEXT,
                    reason TEXT
                )
                """
            )
            # Try to add model_version column if it doesn't exist (SQLite migration fallback)
            try:
                conn.execute("ALTER TABLE paper_trades ADD COLUMN model_version TEXT DEFAULT 'v1'")
            except sqlite3.OperationalError:
                pass


    def submit_order(self, order: OrderContract) -> OrderContract:
        passed, reason, final_size = self.risk_manager.evaluate(order)
        if not passed:
            order.status = OrderStatus.REJECTED
            order.reason = reason
            self._save(order)
            return order
            
        order.size = final_size

        # Fetch execution price
        latest_df = self.engine.latest("realtime_ticks")
        if latest_df.empty:
            latest_df = self.engine.latest("market")
        
        symbol_data = latest_df[latest_df["symbol"] == order.symbol]
        
        # FSE outputs chronologically, so last row is latest price
        execution_price = float(symbol_data.iloc[-1]["price"])
        
        order.status = OrderStatus.FILLED
        order.fill_price = execution_price
        order.fill_timestamp = datetime.now(timezone.utc).isoformat()
        order.reason = "executed_at_market"
        
        self._save(order)
        return order

    def _save(self, order: OrderContract):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO paper_trades 
                (symbol, side, size, strategy_id, model_version, status, fill_price, fill_timestamp, reason)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (order.symbol, order.side.value, order.size, order.strategy_id, order.model_version,
                 order.status.value, order.fill_price, order.fill_timestamp, order.reason)
            )
