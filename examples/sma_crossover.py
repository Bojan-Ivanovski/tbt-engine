import logging
import sys

from tbt_engine import Engine
from tbt_engine.strategies import SmaCrossoverStrategy

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)


def main() -> None:
    strategy = SmaCrossoverStrategy(symbols=["AAPL", "NVDA", "MSFT"])
    result = Engine().start(strategy)
    logger.info(
        "Result: start=%.2f end=%.2f return=%.2f%% trades=%d",
        result.starting_equity,
        result.ending_equity,
        result.total_return_pct,
        len(result.trades),
    )


if __name__ == "__main__":
    main()
