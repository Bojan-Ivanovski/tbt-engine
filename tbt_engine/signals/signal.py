from abc import ABC, abstractmethod

from tbt_engine.asset import Asset
from tbt_engine.orders import ExecutionTime, OrderIntent, Side, SubmitOrder


class Signal(ABC):
    side: Side

    def __init__(self, asset: Asset):
        self.asset = asset

    def to_command(self, execution_time: ExecutionTime = ExecutionTime.NEXT_OPEN) -> SubmitOrder:
        return SubmitOrder(
            OrderIntent(
                symbol=self.asset.symbol,
                side=self.side,
                quantity=self.asset.quantity,
                execution_time=execution_time,
            )
        )

    @abstractmethod
    def _signal_type(self) -> None:
        """Keep the legacy signal base class abstract."""
        raise NotImplementedError
