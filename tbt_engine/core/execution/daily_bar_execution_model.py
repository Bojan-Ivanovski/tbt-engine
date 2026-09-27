from tbt_engine.core.execution.execution_model import (
    ExecutionMarketState,
    ExecutionModel,
    ExecutionOutcome,
    ExecutionOutcomeStatus,
    Fill,
)
from tbt_engine.core.orders import Order


class DailyBarExecutionModel(ExecutionModel):
    """Fully fill market orders at an eligible daily-bar open or close."""

    def execute(self, order: Order, market: ExecutionMarketState) -> ExecutionOutcome:
        price = market.get_price(order.intent.symbol)
        if price is None:
            return ExecutionOutcome(
                status=ExecutionOutcomeStatus.REJECTED,
                remaining_quantity=order.remaining_quantity,
                reason=f"No execution price available for {order.intent.symbol}",
            )
        fill = Fill(
            order_id=order.id,
            symbol=order.intent.symbol,
            side=order.intent.side,
            quantity=order.remaining_quantity,
            price=price,
            time=market.time,
            phase=market.phase,
        )
        return ExecutionOutcome(
            status=ExecutionOutcomeStatus.FILLED,
            remaining_quantity=0,
            fills=(fill,),
        )
