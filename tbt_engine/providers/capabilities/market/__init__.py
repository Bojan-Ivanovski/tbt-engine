"""Shared contracts for market-scoped provider capabilities."""

# pyright: reportUnusedImport=false, reportUnsupportedDunderAll=false
"""Normalized market-context provider capability contracts."""

from .breadth import (
    BREADTH_CAPABILITY,
    BreadthCapability,
    BreadthQuery,
    BreadthRecord,
    BreadthResult,
)
from .market_capabilities import MarketCapabilities
from .market_data import MarketDataAvailability, MarketDataMetadata, MarketDataResult
from .market_identifier import MarketIdentifier
from .nasdaq import (
    NASDAQ_CAPABILITY,
    NasdaqCapability,
    NasdaqMembership,
    NasdaqMembershipScope,
    NasdaqObservation,
    NasdaqObservationKind,
    NasdaqQuery,
    NasdaqResult,
)
from .sector_etf import (
    SECTOR_ETF_CAPABILITY,
    SectorETFCapability,
    SectorETFMapping,
    SectorETFObservation,
    SectorETFObservationKind,
    SectorETFQuery,
    SectorETFResult,
)
from .sp500 import (
    SP500_CAPABILITY,
    SP500Capability,
    SP500ConstituentMembership,
    SP500Interval,
    SP500IntervalAlignment,
    SP500IntervalUnit,
    SP500MembershipScope,
    SP500Observation,
    SP500ObservationType,
    SP500Query,
    SP500Result,
    SP500ValueUnit,
)
from .vix import VIX_CAPABILITY, VIXCapability, VIXQuery, VIXRecord, VIXResult

__all__ = [name for name in globals() if not name.startswith("_")]
