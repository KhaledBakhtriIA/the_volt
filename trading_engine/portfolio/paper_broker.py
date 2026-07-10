from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional


class PaperBroker:
    """SQLite-backed virtual broker for paper trading simulation."""

    def __init__(self, db_path: str, slippage_pct: float = 0.0005):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.slippage_pct = slippage_pct
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        con = sqlite3.connect(self.db_path)
        con.row_factory = sqlite3.Row
        return con

    def _init_db(self) -> None:
        with self._connect() as con:
            con.execute(
                """
                CREATE TABLE IF NOT EXISTS virtual_portfolio (
                    trade_id TEXT PRIMARY KEY,
                    symbol TEXT NOT NULL,
                    direction TEXT NOT NULL,
                    entry_price REAL NOT NULL,
                    quantity REAL NOT NULL,
                    slippage_pct REAL NOT NULL,
                    commission REAL NOT NULL,
                    effective_price REAL NOT NULL,
                    timestamp TEXT NOT NULL,
                    model_version TEXT,
                    status TEXT DEFAULT 'OPEN'
                )
                """
            )

    def execute(
        self,
        symbol: str,
        direction: str,
        quantity: float,
        market_price: float,
        model_version: str | None = None,
    ) -> Dict[str, Any]:
        side = direction.upper().strip()
        if side not in {"BUY", "SELL"}:
            raise ValueError("direction_must_be_buy_or_sell")
        if quantity <= 0:
            raise ValueError("quantity_must_be_positive")
        if market_price <= 0:
            raise ValueError("market_price_must_be_positive")

        if side == "BUY":
            effective_price = market_price * (1.0 + self.slippage_pct)
        else:
            effective_price = market_price * (1.0 - self.slippage_pct)

        commission = 0.001 * quantity * effective_price
        trade_id = str(uuid.uuid4())
        timestamp = datetime.utcnow().isoformat()

        trade = {
            "trade_id": trade_id,
            "symbol": symbol,
            "direction": side,
            "entry_price": float(market_price),
            "quantity": float(quantity),
            "slippage_pct": float(self.slippage_pct),
            "commission": float(commission),
            "effective_price": float(effective_price),
            "timestamp": timestamp,
            "model_version": model_version,
            "status": "OPEN",
        }

        with self._connect() as con:
            con.execute(
                """
                INSERT INTO virtual_portfolio(
                    trade_id, symbol, direction, entry_price, quantity,
                    slippage_pct, commission, effective_price, timestamp,
                    model_version, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    trade["trade_id"],
                    trade["symbol"],
                    trade["direction"],
                    trade["entry_price"],
                    trade["quantity"],
                    trade["slippage_pct"],
                    trade["commission"],
                    trade["effective_price"],
                    trade["timestamp"],
                    trade["model_version"],
                    trade["status"],
                ),
            )

        return trade

    @staticmethod
    def _record_to_mutable(record: sqlite3.Row) -> Dict[str, Any]:
        return {
            "trade_id": record["trade_id"],
            "symbol": record["symbol"],
            "direction": record["direction"],
            "entry_price": float(record["entry_price"]),
            "quantity": float(record["quantity"]),
            "slippage_pct": float(record["slippage_pct"]),
            "commission": float(record["commission"]),
            "effective_price": float(record["effective_price"]),
            "timestamp": record["timestamp"],
            "model_version": record["model_version"],
            "status": record["status"],
        }

    def get_pnl(self, symbol: str | None = None) -> Dict[str, Any]:
        query = """
            SELECT trade_id, symbol, direction, entry_price, quantity,
                   slippage_pct, commission, effective_price, timestamp,
                   model_version, status
            FROM virtual_portfolio
            WHERE status = 'OPEN'
        """
        params: tuple[Any, ...]
        if symbol:
            query += " AND symbol = ?"
            params = (symbol,)
        else:
            params = ()
        query += " ORDER BY timestamp ASC"

        with self._connect() as con:
            rows = con.execute(query, params).fetchall()

        by_symbol: Dict[str, float] = {}
        matched_trades = 0

        for sym in sorted({row["symbol"] for row in rows}):
            sym_rows = [self._record_to_mutable(row) for row in rows if row["symbol"] == sym]
            buy_queue: list[Dict[str, Any]] = []
            sell_queue: list[Dict[str, Any]] = []
            realized = 0.0

            for trade in sym_rows:
                qty_left = float(trade["quantity"])
                side = trade["direction"]
                if side == "BUY":
                    while qty_left > 0 and sell_queue:
                        short_trade = sell_queue[0]
                        match_qty = min(qty_left, short_trade["qty_left"])
                        pnl = (short_trade["effective_price"] - trade["effective_price"]) * match_qty
                        pnl -= short_trade["commission_per_unit"] * match_qty
                        pnl -= trade["commission"] / trade["quantity"] * match_qty
                        realized += pnl
                        matched_trades += 1
                        qty_left -= match_qty
                        short_trade["qty_left"] -= match_qty
                        if short_trade["qty_left"] <= 0:
                            sell_queue.pop(0)
                    if qty_left > 0:
                        buy_queue.append(
                            {
                                "qty_left": qty_left,
                                "effective_price": trade["effective_price"],
                                "commission_per_unit": trade["commission"] / trade["quantity"],
                            }
                        )
                else:
                    while qty_left > 0 and buy_queue:
                        long_trade = buy_queue[0]
                        match_qty = min(qty_left, long_trade["qty_left"])
                        pnl = (trade["effective_price"] - long_trade["effective_price"]) * match_qty
                        pnl -= long_trade["commission_per_unit"] * match_qty
                        pnl -= trade["commission"] / trade["quantity"] * match_qty
                        realized += pnl
                        matched_trades += 1
                        qty_left -= match_qty
                        long_trade["qty_left"] -= match_qty
                        if long_trade["qty_left"] <= 0:
                            buy_queue.pop(0)
                    if qty_left > 0:
                        sell_queue.append(
                            {
                                "qty_left": qty_left,
                                "effective_price": trade["effective_price"],
                                "commission_per_unit": trade["commission"] / trade["quantity"],
                            }
                        )

            by_symbol[sym] = float(realized)

        total_pnl = float(sum(by_symbol.values()))
        return {
            "total_pnl": total_pnl,
            "trades": matched_trades,
            "by_symbol": by_symbol,
        }

    def close_trade(self, trade_id: str, exit_price: float) -> Dict[str, Any]:
        if exit_price <= 0:
            raise ValueError("exit_price_must_be_positive")

        with self._connect() as con:
            row = con.execute(
                """
                SELECT trade_id, symbol, direction, entry_price, quantity,
                       slippage_pct, commission, effective_price, timestamp,
                       model_version, status
                FROM virtual_portfolio
                WHERE trade_id = ?
                """,
                (trade_id,),
            ).fetchone()
            if row is None:
                raise ValueError("trade_not_found")
            if row["status"] != "OPEN":
                raise ValueError("trade_already_closed")

            trade = self._record_to_mutable(row)
            if trade["direction"] == "BUY":
                exit_effective_price = exit_price * (1.0 - trade["slippage_pct"])
                pnl = (exit_effective_price - trade["effective_price"]) * trade["quantity"]
            else:
                exit_effective_price = exit_price * (1.0 + trade["slippage_pct"])
                pnl = (trade["effective_price"] - exit_effective_price) * trade["quantity"]

            exit_commission = 0.001 * trade["quantity"] * exit_effective_price
            pnl -= trade["commission"]
            pnl -= exit_commission

            con.execute(
                "UPDATE virtual_portfolio SET status = ? WHERE trade_id = ?",
                ("CLOSED", trade_id),
            )

        return {
            "trade_id": trade_id,
            "symbol": trade["symbol"],
            "direction": trade["direction"],
            "quantity": trade["quantity"],
            "entry_effective_price": trade["effective_price"],
            "exit_effective_price": float(exit_effective_price),
            "entry_commission": trade["commission"],
            "exit_commission": float(exit_commission),
            "pnl": float(pnl),
            "status": "CLOSED",
        }
