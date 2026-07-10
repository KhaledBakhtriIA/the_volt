import pytest
from trading_engine.strategies.trading_math import calculate_kelly_fraction, verify_alpha_edge, calculate_drawdown

def test_calculate_kelly_fraction_handles_positive_edge():
    # Win prob = 0.6, W = 2, L = 1 => W/L = 2
    # Kelly = 0.6 - (0.4 / 2) = 0.6 - 0.2 = 0.4
    k = calculate_kelly_fraction(0.6, 2.0, 1.0)
    assert pytest.approx(k, 0.01) == 0.4
    
def test_calculate_kelly_fraction_rejects_negative_edge():
    # Win prob = 0.3, W = 1, L = 2 => W/L = 0.5
    # Kelly = 0.3 - (0.7 / 0.5) = 0.3 - 1.4 < 0 => cap at 0
    k = calculate_kelly_fraction(0.3, 1.0, 2.0)
    assert k == 0.0

def test_verify_alpha_edge_survives_costs():
    # Win prob = 0.55, W = 100, L = 100, cost = 2
    # net_win = 98, net_loss = 102
    # expected = (0.55 * 98) - (0.45 * 102) = 53.9 - 45.9 = +8.0
    has_edge, ev = verify_alpha_edge(0.55, 100.0, 100.0, 2.0)
    assert has_edge is True
    assert pytest.approx(ev, 0.1) == 8.0

def test_verify_alpha_edge_killed_by_costs():
    # Win prob = 0.51, W = 10, L = 10, cost = 1.0
    # expected = (0.51 * 9) - (0.49 * 11) = 4.59 - 5.39 = -0.80
    has_edge, ev = verify_alpha_edge(0.51, 10.0, 10.0, 1.0)
    assert has_edge is False
    assert ev < 0.0

def test_calculate_drawdown():
    assert calculate_drawdown(100.0, 80.0) == 0.20
    assert calculate_drawdown(100.0, 110.0) == 0.0
    assert calculate_drawdown(0.0, 10.0) == 0.0
