from tbt_engine.core.ledger import LedgerState
from tbt_engine.core.valuation.valuation_model import (
    PortfolioValuation,
    PositionValuation,
    ValuationMarketState,
    ValuationModel,
)


class ClosePriceValuationModel(ValuationModel):
    @property
    def name(self) -> str:
        return "close_price"

    def value(
        self,
        portfolio: LedgerState,
        market: ValuationMarketState,
    ) -> PortfolioValuation:
        positions: list[PositionValuation] = []
        for symbol, quantity in portfolio.positions:
            price = market.get_price(symbol)
            if price is None:
                raise ValueError(f"No valuation price available for {symbol}")
            positions.append(
                PositionValuation(
                    symbol=symbol,
                    quantity=quantity,
                    price=price,
                    market_value=quantity * price,
                )
            )
        total_equity = portfolio.cash + sum(position.market_value for position in positions)
        return PortfolioValuation(
            time=market.time,
            phase=market.phase,
            model=self.name,
            currency=portfolio.currency,
            cash=portfolio.cash,
            positions=tuple(positions),
            total_equity=total_equity,
        )
