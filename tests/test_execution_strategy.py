from datetime import datetime, timedelta
from src.canonical.execution_strategy import MarketExecution, TWAPExecution

def test_market_execution_generates_one_order():
    start = datetime(2026, 4, 4, 12, 0, 0)
    strategy = MarketExecution()
    orders = strategy.generate_orders(total_size=100.0, current_price=50.0, start_time=start)
    
    assert len(orders) == 1
    assert orders[0].size == 100.0
    assert orders[0].order_type == "MARKET"
    assert orders[0].target_time == start

def test_twap_execution_generates_multiple_orders():
    start = datetime(2026, 4, 4, 12, 0, 0)
    # 30 minutes, 6 slices => 5 min intervals
    strategy = TWAPExecution(duration_minutes=30, slices=6)
    orders = strategy.generate_orders(total_size=120.0, current_price=50.0, start_time=start)
    
    assert len(orders) == 6
    for o in orders:
        assert o.size == 20.0
        assert o.order_type == "MARKET"
        
    assert orders[0].target_time == start
    assert orders[1].target_time == start + timedelta(seconds=300)
    assert orders[-1].target_time == start + timedelta(seconds=1500)

def test_twap_execution_fallback_to_market():
    start = datetime(2026, 4, 4, 12, 0, 0)
    strategy = TWAPExecution(duration_minutes=30, slices=6)
    
    # Very small size, should fallback
    orders = strategy.generate_orders(total_size=2.0, current_price=50.0, start_time=start)
    assert len(orders) == 1
    assert orders[0].size == 2.0
