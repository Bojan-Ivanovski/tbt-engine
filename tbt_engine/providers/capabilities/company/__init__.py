"""Shared contracts for company-scoped provider capabilities."""

# pyright: reportUnusedImport=false, reportUnsupportedDunderAll=false
"""Normalized company-scoped provider capability contracts."""

from .company_capabilities import CompanyCapabilities
from .company_data import CompanyDataAvailability, CompanyDataMetadata, CompanyDataResult
from .company_identifier import CompanyIdentifier
from .company_news import (
    COMPANY_NEWS_CAPABILITY,
    CompanyNewsCapability,
    CompanyNewsQuery,
    CompanyNewsRecord,
    CompanyNewsResult,
)
from .corporate_actions import (
    CORPORATE_ACTIONS_CAPABILITY,
    CorporateActionRecord,
    CorporateActionsCapability,
    CorporateActionsQuery,
    CorporateActionsResult,
    CorporateActionType,
    DividendRecord,
    SplitRecord,
)
from .earnings import (
    EARNINGS_CAPABILITY,
    EarningsActual,
    EarningsCapability,
    EarningsEstimate,
    EarningsEvent,
    EarningsMetricId,
    EarningsQuery,
    EarningsReportingPeriod,
    EarningsResult,
    EarningsSurprise,
    EarningsTimingStatus,
)
from .fundamentals import (
    FUNDAMENTALS_CAPABILITY,
    AccountingBasis,
    CompanyProfileRecord,
    FinancialStatementRecord,
    FinancialStatementType,
    FiscalPeriod,
    FiscalPeriodLabel,
    FundamentalMetricId,
    FundamentalRecordType,
    FundamentalsCapability,
    FundamentalsQuery,
    FundamentalsResult,
    ReportingPeriod,
    ReportingPeriodType,
)
from .ohlcv import (
    OHLCV_CAPABILITY,
    BarInterval,
    BarIntervalUnit,
    OHLCVAdjustment,
    OHLCVBar,
    OHLCVCapability,
    OHLCVQuery,
    OHLCVResult,
)

__all__ = [name for name in globals() if not name.startswith("_")]
