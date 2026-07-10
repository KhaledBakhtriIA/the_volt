import pytest
from trading_engine.risk_management.risk_management import PortfolioRiskModel, RiskProfile, RiskLimitExceeded

def test_portfolio_risk_model_drawdown_kill_switch():
    profile = RiskProfile(max_global_drawdown=0.20)
    model = PortfolioRiskModel(profile)
    
    model.sync_equity(100000.0)
    assert model.peak_equity == 100000.0
    
    # 10% drawdown
    model.sync_equity(90000.0)
    is_halted, _ = model.check_kill_switch()
    assert is_halted is False
    
    # 25% drawdown => > 20%
    model.sync_equity(75000.0)
    is_halted, reason = model.check_kill_switch()
    assert is_halted is True
    assert "exceeds limit" in reason

def test_portfolio_risk_model_position_sizing():
    profile = RiskProfile(
        max_position_size_pct=0.10, 
        kelly_fraction_multiplier=0.50
    )
    model = PortfolioRiskModel(profile)
    model.sync_equity(100000.0)
    
    # Win = 0.6, AvgW=2, AvgL=1 => Kelly=0.4
    # Half-Kelly = 0.2 (20%)
    # Max allowed by profile is 10%, so cap at 10%.
    # Equity = 100k => Capital to deploy = 10k.
    # Price = 50 => Units = 200
    
    units = model.calculate_position_size("BTC", current_price=50.0, win_prob=0.6, avg_win=2.0, avg_loss=1.0)
    assert units == 200.0

def test_portfolio_risk_model_blocks_order_if_halted():
    profile = RiskProfile(max_global_drawdown=0.10)
    model = PortfolioRiskModel(profile)
    model.sync_equity(100000.0)
    model.sync_equity(80000.0) # 20% DD
    
    with pytest.raises(RiskLimitExceeded):
        model.calculate_position_size("BTC", 50.0, 0.6, 2.0, 1.0)
