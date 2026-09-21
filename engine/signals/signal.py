from abc import ABC, abstractmethod

from engine.asset import Asset
from engine.market import MarketState
from engine.portfolio import Portfolio


class Signal(ABC):
    side: str

    def __init__(self, asset: Asset):
        self.asset = asset

    @abstractmethod
    def execute(self, portfolio: Portfolio, market: MarketState) -> bool:
        """Execute the order and return whether it was accepted."""
        raise NotImplementedError
