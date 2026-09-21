from abc import ABC, abstractmethod
from typing import List

from engine.market import MarketState
from engine.portfolio import PortfolioState
from engine.signals.signal import Signal


class Strategy(ABC):
    def __init__(self, name: str):
        self.name = name

    @abstractmethod
    def define_market(self) -> List[str]:
        raise NotImplementedError

    @abstractmethod
    def execute(self, market: MarketState, portfolio: PortfolioState) -> List[Signal]:
        raise NotImplementedError
