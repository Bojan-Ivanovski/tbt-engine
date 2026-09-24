from abc import ABC, abstractmethod

from tbt_engine.market import MarketState
from tbt_engine.portfolio import PortfolioState
from tbt_engine.signals.signal import Signal


class Strategy(ABC):
    def __init__(self, name: str):
        self.name = name

    @abstractmethod
    def define_market(self) -> list[str]:
        raise NotImplementedError

    @abstractmethod
    def execute(self, market: MarketState, portfolio: PortfolioState) -> list[Signal]:
        raise NotImplementedError
