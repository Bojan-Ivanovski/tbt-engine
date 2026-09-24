import logging
import math
from dataclasses import replace
from datetime import date
from enum import Enum

from tbt_engine.market import (
    BeforeOpenMarketState,
    ClosedMarketState,
    Market,
    OpenMarketState,
)
from tbt_engine.orders import (
    ExecutionTime,
    Order,
    OrderEvent,
    OrderEventType,
    OrderId,
    OrderState,
    OrderStatus,
    Side,
    StrategyCommand,
    SubmitOrder,
)
from tbt_engine.portfolio import Portfolio, PortfolioState
from tbt_engine.providers.provider import Provider
from tbt_engine.result import BacktestResult, EquityPoint, Trade
from tbt_engine.strategy import Strategy

logger = logging.getLogger(__name__)


class SimulationPhase(str, Enum):
    BEFORE_OPEN = "before_open"
    OPEN = "open"
    ACTIVE = "active"
    CLOSE = "close"
    AFTER_CLOSE = "after_close"
    END = "end"


class Engine:
    def __init__(
        self,
        provider: Provider | None = None,
        start_date: date = date(2000, 1, 1),
        end_date: date | None = None,
        interval: str = "1d",
        initial_balance: float = 1000.0,
    ):
        if provider is None:
            from tbt_engine.providers.yahoo_provider import YahooProvider

            provider = YahooProvider()

        self.provider = provider
        self.start_date = start_date
        self.end_date = end_date
        self.interval = interval
        self.initial_balance = float(initial_balance)

    def start(self, strategy: Strategy) -> BacktestResult:
        logger.info("Running strategy: %s", strategy.name)
        portfolio = Portfolio(self.initial_balance)
        market = Market(
            provider=self.provider,
            start=self.start_date,
            end=self.end_date,
            interval=self.interval,
        )
        market.set_assets(strategy.define_market())

        trades: list[Trade] = []
        equity_history: list[EquityPoint] = []
        orders: dict[OrderId, Order] = {}
        order_events: list[OrderEvent] = []
        next_order_id = 1

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
                order_events,
                market,
                candle_time,
                SimulationPhase.BEFORE_OPEN,
                next_order_id,
            )

            self._execute_orders(
                orders,
                order_events,
                trades,
                portfolio,
                market,
                candle_time,
                SimulationPhase.OPEN,
                ExecutionTime.NEXT_OPEN,
            )

            open_state = OpenMarketState(market)
            next_order_id = self._process_commands(
                strategy.execute(
                    market=open_state,
                    portfolio=PortfolioState(portfolio),
                    orders=OrderState(orders),
                ),
                orders,
                order_events,
                market,
                candle_time,
                SimulationPhase.ACTIVE,
                next_order_id,
            )

            self._execute_orders(
                orders,
                order_events,
                trades,
                portfolio,
                market,
                candle_time,
                SimulationPhase.CLOSE,
                ExecutionTime.SESSION_CLOSE,
            )

            closed_state = ClosedMarketState(market)
            next_order_id = self._process_commands(
                strategy.after_close(
                    market=closed_state,
                    portfolio=PortfolioState(portfolio),
                    orders=OrderState(orders),
                ),
                orders,
                order_events,
                market,
                candle_time,
                SimulationPhase.AFTER_CLOSE,
                next_order_id,
            )

            equity = portfolio.balance + sum(
                asset.quantity * closed_state.get_latest_closed(symbol)
                for symbol, asset in portfolio.holdings.items()
            )
            equity_history.append(EquityPoint(candle_time, equity))

        final_time = equity_history[-1].time
        for order_id, order in tuple(orders.items()):
            if order.status is OrderStatus.PENDING:
                orders[order_id] = replace(order, status=OrderStatus.EXPIRED)
                order_events.append(
                    OrderEvent(
                        order_id=order_id,
                        time=final_time,
                        phase=SimulationPhase.END.value,
                        type=OrderEventType.EXPIRED,
                        reason="No eligible market event remained",
                    )
                )

        result = BacktestResult(
            starting_equity=self.initial_balance,
            ending_equity=equity_history[-1].equity,
            trades=trades,
            equity_history=equity_history,
            orders=list(orders.values()),
            order_events=order_events,
        )
        logger.info(
            "Finished %s: equity=%.2f return=%.2f%% trades=%d",
            strategy.name,
            result.ending_equity,
            result.total_return_pct,
            len(result.trades),
        )
        return result

    @staticmethod
    def _process_commands(
        commands: list[StrategyCommand],
        orders: dict[OrderId, Order],
        events: list[OrderEvent],
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
                orders[order_id] = Order(
                    id=order_id,
                    intent=intent,
                    status=status,
                    submitted_at=time,
                    submitted_phase=phase.value,
                    eligible_candle=eligible_candle,
                )
                events.append(
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
            if order is not None and order.status is OrderStatus.PENDING:
                orders[command.order_id] = replace(order, status=OrderStatus.CANCELLED)
                event_type = OrderEventType.CANCELLED
                reason = None
            else:
                event_type = OrderEventType.CANCELLATION_REJECTED
                reason = "Order is unknown or no longer cancellable"
            events.append(
                OrderEvent(
                    order_id=command.order_id,
                    time=time,
                    phase=phase.value,
                    type=event_type,
                    reason=reason,
                )
            )
        return next_order_id

    @staticmethod
    def _execute_orders(
        orders: dict[OrderId, Order],
        events: list[OrderEvent],
        trades: list[Trade],
        portfolio: Portfolio,
        market: Market,
        time: str,
        phase: SimulationPhase,
        execution_time: ExecutionTime,
    ) -> None:
        for order_id, order in tuple(orders.items()):
            if (
                order.status is not OrderStatus.PENDING
                or order.intent.execution_time is not execution_time
                or order.eligible_candle > market.current_candle
            ):
                continue

            asset = market.assets[order.intent.symbol]
            price = (
                asset.get_open(market.current_candle)
                if execution_time is ExecutionTime.NEXT_OPEN
                else asset.get_close(market.current_candle)
            )
            if order.intent.side is Side.BUY:
                filled = portfolio.buy(order.intent.symbol, order.intent.quantity, price)
                failure_reason = "Insufficient cash at execution"
            else:
                filled = portfolio.sell(order.intent.symbol, order.intent.quantity, price)
                failure_reason = "Insufficient position at execution"

            if not filled:
                orders[order_id] = replace(order, status=OrderStatus.REJECTED)
                events.append(
                    OrderEvent(
                        order_id=order_id,
                        time=time,
                        phase=phase.value,
                        type=OrderEventType.REJECTED,
                        reason=failure_reason,
                    )
                )
                continue

            orders[order_id] = replace(
                order,
                status=OrderStatus.FILLED,
                filled_at=time,
                fill_price=price,
            )
            events.append(
                OrderEvent(
                    order_id=order_id,
                    time=time,
                    phase=phase.value,
                    type=OrderEventType.FILLED,
                )
            )
            trades.append(
                Trade(
                    time=time,
                    symbol=order.intent.symbol,
                    side=order.intent.side.value,
                    quantity=order.intent.quantity,
                    price=price,
                    order_id=order_id,
                    phase=phase.value,
                )
            )
