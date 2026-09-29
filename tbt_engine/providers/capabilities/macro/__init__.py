"""Shared contracts for macroeconomic provider capabilities."""

# pyright: reportUnusedImport=false, reportUnsupportedDunderAll=false
"""Normalized macroeconomic provider capability contracts."""

from .commodities_fx import (
    COMMODITIES_FX_CAPABILITY,
    CommoditiesFXCapability,
    CommoditiesFXQuery,
    CommoditiesFXRecord,
    CommoditiesFXResult,
    InstrumentKind,
)
from .cpi import CPI_CAPABILITY, CPICapability, CPIQuery, CPIRecord, CPIResult, CPIValueKind
from .gdp import (
    GDP_CAPABILITY,
    GDPCapability,
    GDPMeasure,
    GDPPriceBasis,
    GDPQuery,
    GDPRecord,
    GDPResult,
)
from .interest_rates import (
    INTEREST_RATES_CAPABILITY_ID,
    CompoundingMethod,
    InterestRateCompounding,
    InterestRateInstrumentType,
    InterestRateOrdering,
    InterestRateQuery,
    InterestRateQuotation,
    InterestRateRecord,
    InterestRatesCapability,
    InterestRateTenor,
    TenorUnit,
)
from .macro_capabilities import MacroCapabilities
from .macro_data import (
    MacroDataAvailability,
    MacroDataMetadata,
    MacroDataRecord,
    MacroDataResult,
    MacroRevisionMetadata,
    MacroUnitMetadata,
    ObservationPeriod,
    SeasonalAdjustmentStatus,
)
from .macro_identifier import GeographyIdentifier, MacroSeriesIdentifier
from .unemployment import (
    UNEMPLOYMENT_CAPABILITY,
    UnemploymentCapability,
    UnemploymentMeasure,
    UnemploymentQuery,
    UnemploymentRecord,
    UnemploymentResult,
)

__all__ = [name for name in globals() if not name.startswith("_")]
