from __future__ import annotations

import math
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List

@dataclass
class ChildOrder:
    """Represents a sliced chunk of a parent order."""
    size: float
    target_time: datetime
    order_type: str = "MARKET"
    limit_price: float | None = None

class ExecutionStrategy(ABC):
    """Base interface for algorithmic execution strategies."""
    
    @abstractmethod
    def generate_orders(self, total_size: float, current_price: float, start_time: datetime) -> List[ChildOrder]:
        """Convert a parent order size into a schedule of child orders."""
        pass

class MarketExecution(ExecutionStrategy):
    """Immediate fill execution. Generates a single child order for the full size."""
    
    def generate_orders(self, total_size: float, current_price: float, start_time: datetime) -> List[ChildOrder]:
        if total_size <= 0:
            return []
        
        return [
            ChildOrder(
                size=total_size,
                target_time=start_time,
                order_type="MARKET",
                limit_price=None
            )
        ]

class TWAPExecution(ExecutionStrategy):
    """
    Time-Weighted Average Price.
    Slices the parent order into evenly sized and evenly spaced child orders
    across a defined time window to minimize market impact.
    """
    
    def __init__(self, duration_minutes: int = 30, slices: int = 6):
        self.duration_minutes = duration_minutes
        self.slices = slices

    def generate_orders(self, total_size: float, current_price: float, start_time: datetime) -> List[ChildOrder]:
        if total_size <= 0:
            return []
            
        # If order is too small to slice meaningfully, fallback to market
        if total_size < self.slices:
            return MarketExecution().generate_orders(total_size, current_price, start_time)
            
        chunk_size = total_size / self.slices
        interval_seconds = (self.duration_minutes * 60) / self.slices
        
        child_orders = []
        
        for i in range(self.slices):
            target = start_time + timedelta(seconds=i * interval_seconds)
            child_orders.append(
                ChildOrder(
                    size=chunk_size,
                    target_time=target,
                    order_type="MARKET", # Usually TWAP uses market orders at scheduled times or aggressive limits
                    limit_price=None
                )
            )
            
        return child_orders
