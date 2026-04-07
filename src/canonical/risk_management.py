from __future__ import annotations

import logging
from dataclasses import dataclass

from src.brain.trading_math import calculate_drawdown, calculate_kelly_fraction

logger = logging.getLogger(__name__)

@dataclass
class RiskProfile:
    """Configurable tolerances for the Risk Model."""
    max_global_drawdown: float = 0.20  # Halt all trading if 20% drawdown hit
    max_position_size_pct: float = 0.10  # Max exposure on a single trade (10% equity)
    kelly_fraction_multiplier: float = 0.50  # Half-Kelly for safer compounding
    enforce_alpha_validator: bool = True  # Block trades that fail math expectancy

class RiskLimitExceeded(Exception):
    """Raised when an order violates hard risk constraints."""
    pass

class PortfolioRiskModel:
    """
    Evaluates account equity and enforces position-sizing rules 
    (Drawdown, Kelly Fractions, Gross Exposure).
    """
    
    def __init__(self, profile: RiskProfile | None = None):
        self.profile = profile or RiskProfile()
        self.peak_equity = 0.0
        self.current_equity = 0.0

    def sync_equity(self, active_equity: float) -> None:
        """Update tracker with latest portfolio equity."""
        if active_equity <= 0:
            return
            
        self.current_equity = active_equity
        if active_equity > self.peak_equity:
            self.peak_equity = active_equity

    def get_drawdown(self) -> float:
        """Get current drawdown fraction."""
        return calculate_drawdown(self.peak_equity, self.current_equity)

    def check_kill_switch(self) -> tuple[bool, str]:
        """
        Check if global drawdown limits have been breached.
        Returns (is_halted, reason)
        """
        if self.current_equity == 0:
            return True, "No equity synced. Cannot proceed."
            
        dd = self.get_drawdown()
        if dd >= self.profile.max_global_drawdown:
            reason = f"Global Drawdown {dd*100:.1f}% exceeds limit {self.profile.max_global_drawdown*100:.1f}%"
            logger.error(reason)
            return True, reason
            
        return False, "Active"

    def calculate_position_size(
        self,
        symbol: str, 
        current_price: float, 
        win_prob: float, 
        avg_win: float, 
        avg_loss: float
    ) -> float:
        """
        Calculate the safe order size (in asset units) using Half-Kelly criterion,
        capped by gross exposure limits.
        """
        is_halted, reason = self.check_kill_switch()
        if is_halted:
            raise RiskLimitExceeded(reason)

        kf = calculate_kelly_fraction(win_prob, avg_win, avg_loss)
        
        # Apply Kelly multiplier (fractional Kelly) for safety
        target_allocation_pct = kf * self.profile.kelly_fraction_multiplier
        
        # Cap at gross exposure limit
        final_allocation_pct = min(target_allocation_pct, self.profile.max_position_size_pct)
        
        # Dollar sizing
        capital_to_deploy = self.current_equity * final_allocation_pct
        
        if current_price <= 0:
            return 0.0
            
        units = capital_to_deploy / current_price
        return units
