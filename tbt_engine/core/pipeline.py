import math
from dataclasses import replace
from enum import Enum

from tbt_engine.core.collection import ResultCollector
from tbt_engine.core.costs import CostedFill, TransactionCostModel
from tbt_engine.core.execution import (
    ExecutionMarketState,
    ExecutionModel,
    ExecutionOutcome,
    ExecutionOutcomeStatus,
    ExecutionPhase,
    Fill,
    FillId,
)
from tbt_engine.core.ledger import LedgerState
from tbt_engine.core.market import (
    BeforeOpenMarketState,
    ClosedMarketState,
    Market,
    OpenMarketState,
)
from tbt_engine.core.orders import (
    ExecutionTime,
    Order,
    OrderEvent,
    OrderEventType,
    OrderId,
    OrderState,
    OrderStatus,
    StrategyCommand,
    SubmitOrder,
)
from tbt_engine.core.portfolio import Portfolio, PortfolioState
from tbt_engine.core.result import BacktestResult
from tbt_engine.core.strategy import Strategy
from tbt_engine.core.valuation import (
    PortfolioValuation,
    ValuationMarketState,
    ValuationModel,
    ValuationPhase,
)


class SimulationPhase(str, Enum):
    BEFORE_OPEN = "before_open"
    OPEN = "open"
    ACTIVE = "active"
    CLOSE = "close"
    AFTER_CLOSE = "after_close"
    END = "end"


class SimulationPipeline:
    """Run the deterministic market-session lifecycle over prepared state."""

    def __init__(
        self,
        *,
        execution_model: ExecutionModel,
        transaction_cost_model: TransactionCostModel,
        valuation_model: ValuationModel,
        result_collector: ResultCollector,
    ) -> None:
        self.execution_model = execution_model
        self.transaction_cost_model = transaction_cost_model
        self.valuation_model = valuation_model
        self.result_collector = result_collector

    def run(
        self,
        strategy: Strategy,
        market: Market,
        portfolio: Portfolio,
    ) -> BacktestResult:
        collector = self.result_collector
        opening_entry = portfolio.ledger.entries[0]
        collector.begin(opening_entry.cash_delta)
        collector.collect(opening_entry)
        orders: dict[OrderId, Order] = {}
        next_order_id = 1
        next_fill_id = 1
        final_time: str | None = None

        while market.next_candle() < market.final_candle:
            before_open = BeforeOpenMarketState(market)
            candle_time = before_open.get_market_time_iso()
            next_order_id = self._process_commands(
                strategy.before_open(
                    market=before_open,
                    portfolio=PortfolioState(portfolio),
                    orders=OrderState(orders),
                ),
                orders,
                market,
                candle_time,
                SimulationPhase.BEFORE_OPEN,
                next_order_id,
            )

            next_fill_id = self._execute_orders(
                orders,
                portfolio,
                market,
                candle_time,
                SimulationPhase.OPEN,
                ExecutionTime.NEXT_OPEN,
                next_fill_id,
            )

            open_state = OpenMarketState(market)
            next_order_id = self._process_commands(
                strategy.execute(
                    market=open_state,
                    portfolio=PortfolioState(portfolio),
                    orders=OrderState(orders),
                ),
                orders,
                market,
                candle_time,
                SimulationPhase.ACTIVE,
                next_order_id,
            )

            next_fill_id = self._execute_orders(
                orders,
                portfolio,
                market,
                candle_time,
                SimulationPhase.CLOSE,
                ExecutionTime.SESSION_CLOSE,
                next_fill_id,
            )

            closed_state = ClosedMarketState(market)
            next_order_id = self._process_commands(
                strategy.after_close(
                    market=closed_state,
                    portfolio=PortfolioState(portfolio),
                    orders=OrderState(orders),
                ),
                orders,
                market,
                candle_time,
                SimulationPhase.AFTER_CLOSE,
                next_order_id,
            )

            valuation_market = ValuationMarketState(
                time=candle_time,
                phase=ValuationPhase.CLOSE,
                prices={symbol: closed_state.get_latest_closed(symbol) for symbol in market.assets},
            )
            valuation = self.valuation_model.value(
                portfolio.ledger.state,
                valuation_market,
            )
            self._validate_valuation(
                valuation,
                portfolio.ledger.state,
                valuation_market,
            )
            collector.collect(valuation)
            final_time = valuation.time

        if final_time is None:
            raise RuntimeError("Simulation produced no valuation events")
        for order_id, order in tuple(orders.items()):
            if order.status in {OrderStatus.PENDING, OrderStatus.PARTIALLY_FILLED}:
                expired_order = replace(order, status=OrderStatus.EXPIRED)
                orders[order_id] = expired_order
                collector.collect(expired_order)
                collector.collect(
                    OrderEvent(
                        order_id=order_id,
                        time=final_time,
                        phase=SimulationPhase.END.value,
                        type=OrderEventType.EXPIRED,
                        reason="No eligible market event remained",
                    )
                )

        return collector.finalize()

    def _process_commands(
        self,
        commands: list[StrategyCommand],
        orders: dict[OrderId, Order],
        market: Market,
        time: str,
        phase: SimulationPhase,
        next_order_id: int,
    ) -> int:
        for command in commands:
            if isinstance(command, SubmitOrder):
                order_id = OrderId(next_order_id)
                next_order_id += 1
                intent = command.intent
                reason: str | None = None
                if intent.symbol not in market.assets:
                    reason = f"Unknown market symbol: {intent.symbol}"
                elif not math.isfinite(intent.quantity) or intent.quantity <= 0:
                    reason = "Order quantity must be finite and greater than zero"
                elif (
                    intent.execution_time is ExecutionTime.SESSION_CLOSE
                    and phase is SimulationPhase.AFTER_CLOSE
                ):
                    reason = "The current session has already closed"

                eligible_candle = market.current_candle
                if (
                    intent.execution_time is ExecutionTime.NEXT_OPEN
                    and phase is not SimulationPhase.BEFORE_OPEN
                ):
                    eligible_candle += 1

                status = OrderStatus.REJECTED if reason is not None else OrderStatus.PENDING
                submitted_order = Order(
                    id=order_id,
                    intent=intent,
                    status=status,
                    submitted_at=time,
                    submitted_phase=phase.value,
                    eligible_candle=eligible_candle,
                )
                orders[order_id] = submitted_order
                self.result_collector.collect(submitted_order)
                self.result_collector.collect(
                    OrderEvent(
                        order_id=order_id,
                        time=time,
                        phase=phase.value,
                        type=(
                            OrderEventType.REJECTED
                            if reason is not None
                            else OrderEventType.ACCEPTED
                        ),
                        reason=reason,
                    )
                )
                continue

            order = orders.get(command.order_id)
            if order is not None and order.status in {
                OrderStatus.PENDING,
                OrderStatus.PARTIALLY_FILLED,
            }:
                cancelled_order = replace(order, status=OrderStatus.CANCELLED)
                orders[command.order_id] = cancelled_order
                self.result_collector.collect(cancelled_order)
                event_type = OrderEventType.CANCELLED
                reason = None
            else:
                event_type = OrderEventType.CANCELLATION_REJECTED
                reason = "Order is unknown or no longer cancellable"
            self.result_collector.collect(
                OrderEvent(
                    order_id=command.order_id,
                    time=time,
                    phase=phase.value,
                    type=event_type,
                    reason=reason,
                )
            )
        return next_order_id

    def _execute_orders(
        self,
        orders: dict[OrderId, Order],
        portfolio: Portfolio,
        market: Market,
        time: str,
        phase: SimulationPhase,
        execution_time: ExecutionTime,
        next_fill_id: int,
    ) -> int:
        execution_phase = (
            ExecutionPhase.OPEN
            if execution_time is ExecutionTime.NEXT_OPEN
            else ExecutionPhase.CLOSE
        )
        execution_market = ExecutionMarketState(
            time=time,
            phase=execution_phase,
            prices={
                symbol: (
                    asset.get_open(market.current_candle)
                    if execution_phase is ExecutionPhase.OPEN
                    else asset.get_close(market.current_candle)
                )
                for symbol, asset in market.assets.items()
            },
        )
        for order_id, order in tuple(orders.items()):
            if (
                order.status not in {OrderStatus.PENDING, OrderStatus.PARTIALLY_FILLED}
                or order.intent.execution_time is not execution_time
                or order.eligible_candle > market.current_candle
            ):
                continue

            outcome = self.execution_model.execute(order, execution_market)
            self._validate_execution_outcome(order, outcome, execution_market)

            if outcome.status is ExecutionOutcomeStatus.NO_FILL:
                self.result_collector.collect(
                    OrderEvent(
                        order_id=order_id,
                        time=time,
                        phase=phase.value,
                        type=OrderEventType.NO_FILL,
                        reason=outcome.reason,
                    )
                )
                continue

            if outcome.status is ExecutionOutcomeStatus.REJECTED:
                rejected_order = replace(order, status=OrderStatus.REJECTED)
                orders[order_id] = rejected_order
                self.result_collector.collect(rejected_order)
                self.result_collector.collect(
                    OrderEvent(
                        order_id=order_id,
                        time=time,
                        phase=phase.value,
                        type=OrderEventType.REJECTED,
                        reason=outcome.reason,
                    )
                )
                continue

            costed_fills = tuple(
                self.transaction_cost_model.apply(
                    replace(fill, id=FillId(next_fill_id + index)),
                    execution_market,
                    is_first_fill_for_order=(order.filled_quantity == 0 and index == 0),
                )
                for index, fill in enumerate(outcome.fills)
            )
            for index, costed_fill in enumerate(costed_fills):
                expected_fill = replace(outcome.fills[index], id=FillId(next_fill_id + index))
                self._validate_costed_fill(expected_fill, costed_fill)

            posting = portfolio.post(costed_fills)
            if not posting.accepted:
                rejected_order = replace(order, status=OrderStatus.REJECTED)
                orders[order_id] = rejected_order
                self.result_collector.collect(rejected_order)
                self.result_collector.collect(
                    OrderEvent(
                        order_id=order_id,
                        time=time,
                        phase=phase.value,
                        type=OrderEventType.REJECTED,
                        reason=posting.reason,
                    )
                )
                continue

            for costed_fill in costed_fills:
                self.result_collector.collect(costed_fill.fill)
                self.result_collector.collect(costed_fill.cost)
            for entry in posting.entries:
                self.result_collector.collect(entry)
            next_fill_id += len(costed_fills)

            order_status = (
                OrderStatus.FILLED
                if outcome.status is ExecutionOutcomeStatus.FILLED
                else OrderStatus.PARTIALLY_FILLED
            )
            updated_order = replace(
                order,
                status=order_status,
                filled_quantity=order.intent.quantity - outcome.remaining_quantity,
            )
            orders[order_id] = updated_order
            self.result_collector.collect(updated_order)
            self.result_collector.collect(
                OrderEvent(
                    order_id=order_id,
                    time=time,
                    phase=phase.value,
                    type=(
                        OrderEventType.FILLED
                        if order_status is OrderStatus.FILLED
                        else OrderEventType.PARTIALLY_FILLED
                    ),
                    reason=outcome.reason,
                )
            )
        return next_fill_id

    def _validate_valuation(
        self,
        valuation: PortfolioValuation,
        portfolio: LedgerState,
        market: ValuationMarketState,
    ) -> None:
        valued_positions = {position.symbol: position.quantity for position in valuation.positions}
        if valuation.model != self.valuation_model.name:
            raise ValueError("Valuation identifies a different model")
        if valuation.time != market.time or valuation.phase is not market.phase:
            raise ValueError("Valuation time or phase does not match the market snapshot")
        if valuation.currency != portfolio.currency:
            raise ValueError("Valuation currency does not match the portfolio")
        if not math.isclose(
            valuation.cash,
            portfolio.cash,
            rel_tol=1e-12,
            abs_tol=1e-12,
        ):
            raise ValueError("Valuation cash does not match the portfolio")
        if valued_positions != portfolio.as_positions():
            raise ValueError("Valuation positions do not match the portfolio")

    def _validate_costed_fill(self, expected: Fill, actual: CostedFill) -> None:
        if actual.cost.model != self.transaction_cost_model.name:
            raise ValueError("Execution cost identifies a different transaction cost model")
        if (
            actual.fill.id != expected.id
            or actual.fill.order_id != expected.order_id
            or actual.fill.symbol != expected.symbol
            or actual.fill.side is not expected.side
            or actual.fill.quantity != expected.quantity
            or actual.fill.time != expected.time
            or actual.fill.phase is not expected.phase
            or actual.fill.reference_price != expected.reference_price
        ):
            raise ValueError(
                "Transaction cost model changed fill fields other than execution price"
            )

    @staticmethod
    def _validate_execution_outcome(
        order: Order,
        outcome: ExecutionOutcome,
        market: ExecutionMarketState,
    ) -> None:
        executed_quantity = sum(fill.quantity for fill in outcome.fills)
        expected_remaining = order.remaining_quantity - executed_quantity
        if expected_remaining < -1e-12:
            raise ValueError(f"Execution model overfilled order {order.id}")
        if not math.isclose(
            outcome.remaining_quantity,
            max(0.0, expected_remaining),
            rel_tol=1e-12,
            abs_tol=1e-12,
        ):
            raise ValueError(f"Execution model returned inconsistent quantity for order {order.id}")
        for fill in outcome.fills:
            if fill.order_id != order.id:
                raise ValueError("Fill references a different order")
            if fill.symbol != order.intent.symbol or fill.side is not order.intent.side:
                raise ValueError("Fill instrument or side does not match its order")
            if fill.time != market.time or fill.phase is not market.phase:
                raise ValueError("Fill time or phase does not match the execution event")
