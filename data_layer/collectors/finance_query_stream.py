from __future__ import annotations

from typing import Dict, List


class FinanceQueryStream:
    """Optional helper for Finance Query WebSocket streaming configuration."""

    def __init__(self, enabled: bool, ws_url: str, channels: List[str]) -> None:
        self.enabled = enabled
        self.ws_url = ws_url
        self.channels = channels

    def build_subscription(self, symbols: List[str]) -> Dict[str, object]:
        """Build a generic subscription payload for real-time symbols."""
        return {
            "action": "subscribe",
            "channels": self.channels,
            "symbols": symbols,
        }

    def stream_config(self, symbols: List[str]) -> Dict[str, object]:
        """Return stream-ready configuration for external websocket clients."""
        return {
            "enabled": self.enabled,
            "ws_url": self.ws_url,
            "subscription": self.build_subscription(symbols),
        }
