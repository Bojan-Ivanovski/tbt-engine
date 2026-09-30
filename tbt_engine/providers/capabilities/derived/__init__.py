"""Shared contracts for normalized derived-data provider capabilities."""

# pyright: reportUnusedImport=false, reportUnsupportedDunderAll=false
"""Normalized derived-data provider capability contracts."""

from .atr import ATR_CAPABILITY, ATRCapability, ATRQuery, ATRRecord, ATRResult, ATRSmoothing
from .calculations import CalculationIdentity, CalculationParameter
from .capabilities import DERIVED_CAPABILITY_IDS, DerivedCapabilities
from .inputs import DerivedInput, InputSeriesRef, SeriesQualifier, normalize_inputs
from .macd import MACD_CAPABILITY, MACDCapability, MACDQuery, MACDRecord, MACDResult
from .moving_averages import (
    EMA_CAPABILITY,
    SMA_CAPABILITY,
    EMACapability,
    MovingAverageKind,
    MovingAverageQuery,
    MovingAverageRecord,
    MovingAverageResult,
    SMACapability,
)
from .results import (
    DerivedDataAvailability,
    DerivedDataRequestContext,
    DerivedDataResult,
    DerivedOutputIdentity,
    DerivedRecordMetadata,
    EarlyOutputHandling,
    InputProvenance,
    InsufficientWarmUpHandling,
    WarmUpMetadata,
    WarmUpRequirement,
    require_finite,
)
from .returns import (
    RETURNS_CAPABILITY,
    ReturnMethod,
    ReturnsCapability,
    ReturnsQuery,
    ReturnsRecord,
    ReturnsResult,
)
from .rsi import RSI_CAPABILITY, RSICapability, RSIQuery, RSIRecord, RSIResult
from .volatility import (
    VOLATILITY_CAPABILITY,
    VolatilityCapability,
    VolatilityQuery,
    VolatilityRecord,
    VolatilityResult,
    VolatilityReturnMethod,
)

__all__ = [name for name in globals() if not name.startswith("_")]
