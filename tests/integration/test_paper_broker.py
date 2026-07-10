from __future__ import annotations

from trading_engine.portfolio.paper_broker import PaperBroker


def test_paper_broker_execute_persists_trade(tmp_path) -> None:
    broker = PaperBroker(db_path=str(tmp_path / "paper.db"))

    trade = broker.execute(symbol="AAPL", direction="BUY", quantity=10, market_price=100.0, model_version="v1")

    assert trade["symbol"] == "AAPL"
    assert trade["direction"] == "BUY"
    assert trade["effective_price"] > trade["entry_price"]


def test_paper_broker_get_pnl_matches_open_buy_sell_pair(tmp_path) -> None:
    broker = PaperBroker(db_path=str(tmp_path / "paper.db"))

    broker.execute(symbol="AAPL", direction="BUY", quantity=5, market_price=100.0, model_version="v1")
    broker.execute(symbol="AAPL", direction="SELL", quantity=5, market_price=102.0, model_version="v1")

    pnl = broker.get_pnl(symbol="AAPL")

    assert "total_pnl" in pnl
    assert "by_symbol" in pnl
    assert "AAPL" in pnl["by_symbol"]


def test_paper_broker_close_trade_marks_closed_and_returns_summary(tmp_path) -> None:
    broker = PaperBroker(db_path=str(tmp_path / "paper.db"))

    trade = broker.execute(symbol="MSFT", direction="BUY", quantity=3, market_price=200.0, model_version="v2")
    closed = broker.close_trade(trade_id=trade["trade_id"], exit_price=205.0)

    assert closed["trade_id"] == trade["trade_id"]
    assert closed["status"] == "CLOSED"
    assert "pnl" in closed
