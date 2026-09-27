"""Result-collection contracts and implementations."""

from tbt_engine.core.collection.in_memory_result_collector import (
    InMemoryResultCollector,
)
from tbt_engine.core.collection.result_collector import ResultCollector, SimulationRecord

__all__ = [
    "InMemoryResultCollector",
    "ResultCollector",
    "SimulationRecord",
]
