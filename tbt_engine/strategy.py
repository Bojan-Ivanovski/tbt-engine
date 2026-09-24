from abc import ABC, abstractmethod

from tbt_engine.market import BeforeOpenMarketState, ClosedMarketState, OpenMarketState
from tbt_engine.orders import OrderState, StrategyCommand
from tbt_engine.portfolio import PortfolioState


class Strategy(ABC):
    def __init__(self, name: str):
        self.name = name

    @abstractmethod
    def define_market(self) -> list[str]:
        raise NotImplementedError

    def before_open(
        self,
        market: BeforeOpenMarketState,
        portfolio: PortfolioState,
        orders: OrderState,
    ) -> list[StrategyCommand]:
        return []

    def execute(
        self,
        market: OpenMarketState,
        portfolio: PortfolioState,
        orders: OrderState,
    ) -> list[StrategyCommand]:
        return []

    def after_close(
        self,
        market: ClosedMarketState,
        portfolio: PortfolioState,
        orders: OrderState,
    ) -> list[StrategyCommand]:
        return []
