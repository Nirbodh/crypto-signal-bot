import logging
from typing import Dict, List

from app.data.market_data import MarketDataEngine


logger = logging.getLogger("crypto-signal-bot")


class CoinUniverseEngine:
    """
    Builds a clean and liquid USDT coin universe
    from Binance, MEXC and KuCoin.

    This layer does NOT make trading decisions.
    It only decides which assets deserve deeper analysis.
    """

    STABLECOINS = {
        "USDT",
        "USDC",
        "FDUSD",
        "TUSD",
        "USDE",
        "DAI",
        "PYUSD",
        "USD1",
        "USDD",
    }

    LEVERAGED_KEYWORDS = (
        "UP/",
        "DOWN/",
        "BULL/",
        "BEAR/",
        "3L/",
        "3S/",
        "5L/",
        "5S/",
        "2L/",
        "2S/",
    )

    def __init__(
        self,
        market_data: MarketDataEngine,
    ):
        self.market_data = market_data

    def is_valid_symbol(
        self,
        symbol: str,
        market: Dict,
    ) -> bool:
        """
        Basic market-quality filter.
        """

        if not symbol.endswith("/USDT"):
            return False

        base = symbol.split("/")[0].upper()

        # Stablecoin pairs
        if base in self.STABLECOINS:
            return False

        # Leveraged / synthetic tokens
        upper_symbol = symbol.upper()

        if any(
            keyword in upper_symbol
            for keyword in self.LEVERAGED_KEYWORDS
        ):
            return False

        # Must be spot
        if not market.get("spot", False):
            return False

        # Must be active
        if market.get("active", True) is False:
            return False

        return True

    def get_exchange_universe(
        self,
        exchange_name: str,
    ) -> List[str]:
        """
        Get valid USDT spot symbols from one exchange.
        """

        exchange = self.market_data.exchanges.get(
            exchange_name
        )

        if exchange is None:
            return []

        try:
            markets = exchange.load_markets()

            symbols = []

            for symbol, market in markets.items():

                if self.is_valid_symbol(
                    symbol,
                    market,
                ):
                    symbols.append(symbol)

            logger.info(
                "🪙 %s valid USDT pairs: %s",
                exchange_name,
                len(symbols),
            )

            return symbols

        except Exception as exc:

            logger.error(
                "❌ Universe failed for %s: %s",
                exchange_name,
                exc,
            )

            return []

    def build_cross_exchange_universe(self) -> List[str]:
        """
        Combine symbols from Binance, MEXC and KuCoin.
        """

        exchanges = [
            "binance",
            "mexc",
            "kucoin",
        ]

        all_symbols = set()

        for exchange_name in exchanges:

            symbols = self.get_exchange_universe(
                exchange_name
            )

            all_symbols.update(symbols)

        result = sorted(all_symbols)

        logger.info(
            "🌐 Cross-exchange universe: %s",
            len(result),
        )

        return result
