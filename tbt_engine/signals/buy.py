from tbt_engine.orders import Side
from tbt_engine.signals.signal import Signal


class Buy(Signal):
    side = Side.BUY

    def _signal_type(self) -> None:
        return None
