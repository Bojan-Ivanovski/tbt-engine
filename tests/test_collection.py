import unittest

from tbt_engine import (
    Engine,
    EquityPoint,
    InitialPortfolio,
    InMemoryResultCollector,
    LedgerEntry,
    OrderEventType,
    SimulationRecord,
)
from tests.test_simulation_pipeline import InMemoryProvider, NextOpenStrategy


class RecordingResultCollector(InMemoryResultCollector):
    def __init__(self) -> None:
        super().__init__()
        self.record_types: list[str] = []

    def begin(self, starting_equity: float) -> None:
        self.record_types = []
        super().begin(starting_equity)

    def collect(self, record: SimulationRecord) -> None:
        self.record_types.append(type(record).__name__)
        super().collect(record)


class ResultCollectionTests(unittest.TestCase):
    def test_default_collector_derives_trades_from_fills(self) -> None:
        result = Engine(
            provider=InMemoryProvider(), initial_portfolio=InitialPortfolio(cash=100)
        ).start(NextOpenStrategy())

        self.assertEqual(len(result.trades), len(result.fills))
        self.assertEqual(result.trades[0].time, result.fills[0].time)
        self.assertEqual(result.trades[0].symbol, result.fills[0].symbol)
        self.assertEqual(result.trades[0].side, result.fills[0].side.value)
        self.assertEqual(result.trades[0].quantity, result.fills[0].quantity)
        self.assertEqual(result.trades[0].price, result.fills[0].price)
        self.assertEqual(result.trades[0].order_id, result.fills[0].order_id)

    def test_default_collector_derives_equity_history_from_valuations(self) -> None:
        result = Engine(
            provider=InMemoryProvider(), initial_portfolio=InitialPortfolio(cash=100)
        ).start(NextOpenStrategy())

        self.assertEqual(
            result.equity_history,
            [
                EquityPoint(valuation.time, valuation.total_equity)
                for valuation in result.valuations
            ],
        )
        self.assertEqual(result.ending_equity, result.valuations[-1].total_equity)

    def test_injected_collector_observes_records_in_deterministic_order(self) -> None:
        collector = RecordingResultCollector()

        result = Engine(
            provider=InMemoryProvider(),
            initial_portfolio=InitialPortfolio(cash=100),
            result_collector=collector,
        ).start(NextOpenStrategy())

        self.assertEqual(
            collector.record_types,
            [
                "LedgerEntry",
                "Order",
                "OrderEvent",
                "PortfolioValuation",
                "Fill",
                "ExecutionCost",
                "LedgerEntry",
                "Order",
                "OrderEvent",
                "PortfolioValuation",
                "PortfolioValuation",
            ],
        )
        self.assertEqual(result.order_events[0].type, OrderEventType.ACCEPTED)
        self.assertEqual(result.order_events[-1].type, OrderEventType.FILLED)
        self.assertIsInstance(collector.records[0], LedgerEntry)

    def test_collector_resets_cleanly_for_each_run(self) -> None:
        collector = RecordingResultCollector()
        engine = Engine(
            provider=InMemoryProvider(),
            initial_portfolio=InitialPortfolio(cash=100),
            result_collector=collector,
        )

        first = engine.start(NextOpenStrategy())
        first_record_count = len(collector.records)
        second = engine.start(NextOpenStrategy())

        self.assertEqual(len(collector.records), first_record_count)
        self.assertEqual(first, second)

    def test_collector_rejects_calls_outside_run_lifecycle(self) -> None:
        collector = InMemoryResultCollector()

        with self.assertRaisesRegex(RuntimeError, "has not started"):
            collector.finalize()


if __name__ == "__main__":
    unittest.main()
