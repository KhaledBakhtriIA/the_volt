from __future__ import annotations

def calculate_kelly_fraction(win_probability: float, average_win: float, average_loss: float) -> float:
    """
    Calculate the optimal Kelly bet size fraction.
    
    Formula: f* = p - (1 - p) / (W / L)
    Where:
        p = win probability (0.0 to 1.0)
        W = average win amount
        L = average loss amount (positive value)
    
    Returns 0.0 if the calculated fraction is negative (negative edge) or if loss/duration parameters are invalid.
    """
    if win_probability <= 0.0 or win_probability >= 1.0:
        return 0.0
    if average_win <= 0.0 or average_loss <= 0.0:
        return 0.0
        
    win_loss_ratio = average_win / average_loss
    kelly = win_probability - ((1.0 - win_probability) / win_loss_ratio)
    
    return max(0.0, kelly)

def verify_alpha_edge(win_probability: float, average_win: float, average_loss: float, round_trip_cost: float) -> tuple[bool, float]:
    """
    Verify if a trading signal has a mathematical edge that survives transaction costs.
    
    Calculates the expected per-trade net profit considering slippage and commissions.
    
    Returns:
        (has_edge: bool, expectancy: float)
    """
    if win_probability <= 0.0 or average_win <= 0.0 or average_loss <= 0.0:
        return False, 0.0
        
    # Cost is paid regardless of winning or losing
    net_avg_win = average_win - round_trip_cost
    net_avg_loss = average_loss + round_trip_cost
    
    expectancy = (win_probability * net_avg_win) - ((1.0 - win_probability) * net_avg_loss)
    
    return expectancy > 0.0, expectancy

def calculate_drawdown(peak_equity: float, current_equity: float) -> float:
    """
    Calculate the current drawdown percentage from an equity peak.
    
    Returns:
        Drawdown as a positive fraction (e.g., 0.15 represents 15% drawdown)
    """
    if peak_equity <= 0.0:
        return 0.0
    if current_equity >= peak_equity:
        return 0.0
        
    return (peak_equity - current_equity) / peak_equity
