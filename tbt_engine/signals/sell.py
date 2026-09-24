from tbt_engine.orders import Side
from tbt_engine.signals.signal import Signal


class Sell(Signal):
    side = Side.SELL

    def _signal_type(self) -> None:
        return None
