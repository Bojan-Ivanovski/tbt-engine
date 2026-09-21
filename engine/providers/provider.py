from abc import ABC, abstractmethod
from datetime import date
from typing import Optional

import pandas as pd


class Provider(ABC):
    @abstractmethod
    def get_history(
        self,
        symbol: str,
        interval: str = "1d",
        start: Optional[date] = None,
        end: Optional[date] = None,
    ) -> pd.DataFrame:
        raise NotImplementedError
