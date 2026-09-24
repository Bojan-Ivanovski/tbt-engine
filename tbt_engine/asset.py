from dataclasses import dataclass


@dataclass
class Asset:
    symbol: str
    quantity: float = 0.0

    def __post_init__(self):
        self.symbol = self.symbol.upper()
        self.quantity = float(self.quantity)

    def __add__(self, asset: "Asset"):
        self.quantity += asset.quantity
        return self

    def __sub__(self, asset: "Asset"):
        if self.quantity >= asset.quantity:
            self.quantity -= asset.quantity
        return self

    def __repr__(self):
        return f"{self.symbol} - {self.quantity}"

    def __mul__(self, price: float) -> float:
        return self.quantity * price
