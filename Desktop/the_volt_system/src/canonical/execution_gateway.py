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
    model_version: str = "v1"
    status: OrderStatus = OrderStatus.PENDING
    fill_price: Optional[float] = None
    fill_timestamp: Optional[str] = None
    reason: Optional[str] = None

class RiskManager:
    """Gatekeeper that checks FSE for Market Health before allowing orders."""

    def __init__(self, engine: FeatureStoreEngine, max_order_size: float = 1000.0):
        self.engine = engine
        self.max_order_size = max_order_size

    def evaluate(self, order: OrderContract) -> Tuple[bool, str]:
        if order.size <= 0:
            return False, "invalid_size_less_than_zero"
        if order.size > self.max_order_size:
            return False, "exceeds_max_order_size"
        
        # Pull latest cache from the Feature Store Engine
        latest_df = self.engine.latest("realtime_ticks")
        if latest_df.empty:
            # Fallback to batch market data
            latest_df = self.engine.latest("market")
            if latest_df.empty:
                return False, "no_recent_market_data"

        # Ensure we have data for the targeted symbol
        symbol_data = latest_df[latest_df["symbol"] == order.symbol]
        if symbol_data.empty:
            return False, "no_data_for_symbol"

        return True, "passed_risk_checks"


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
        passed, reason = self.risk_manager.evaluate(order)
        if not passed:
            order.status = OrderStatus.REJECTED
            order.reason = reason
            self._save(order)
            return order

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
