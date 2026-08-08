import logging
from typing import Any, Dict, List

import requests


logger = logging.getLogger("crypto-signal-bot")


class CoinUniverseEngine:
    """
    Builds a broad USDT spot trading universe.

    Goals:
        - Include high-cap coins
        - Include mid-cap coins
        - Include lower-cap coins with meaningful liquidity
        - Avoid stablecoins
        - Avoid leveraged/synthetic tokens
        - Aggregate Binance, MEXC and KuCoin
        - Avoid allowing only the highest-volume coins to dominate
          the first scan batch

    This layer selects assets for analysis.
    It does NOT generate trading signals.
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
        "BUSD",
        "EUR",
        "EURC",
    }

    LEVERAGED_TOKENS = (
        "UPUSDT",
        "DOWNUSDT",
        "BULLUSDT",
        "BEARUSDT",
    )

    def __init__(
        self,
        timeout: int = 10,
        min_quote_volume: float = 250_000,
        max_coins: int = 500,
    ) -> None:

        self.timeout = max(
            5,
            int(timeout),
        )

        self.min_quote_volume = max(
            0.0,
            float(min_quote_volume),
        )

        self.max_coins = max(
            1,
            int(max_coins),
        )

        self.session = requests.Session()

    # ==========================================================
    # Helpers
    # ==========================================================

    @staticmethod
    def _is_valid_base(
        base: str,
    ) -> bool:

        base = str(
            base or ""
        ).upper().strip()

        if not base:
            return False

        if base in CoinUniverseEngine.STABLECOINS:
            return False

        return True

    @classmethod
    def _is_leveraged(
        cls,
        symbol: str,
    ) -> bool:

        symbol = str(
            symbol or ""
        ).upper()

        return any(
            token in symbol
            for token in cls.LEVERAGED_TOKENS
        )

    # ==========================================================
    # HTTP
    # ==========================================================

    def _get(
        self,
        url: str,
        params: Dict[str, Any] = None,
    ) -> Any:

        try:

            response = self.session.get(
                url,
                params=params or {},
                timeout=self.timeout,
            )

            response.raise_for_status()

            return response.json()

        except requests.RequestException as exc:

            logger.warning(
                "Public API request failed | %s | %s",
                url,
                exc,
            )

            return None

    # ==========================================================
    # Binance
    # ==========================================================

    def _binance(
        self,
    ) -> List[Dict[str, Any]]:

        data = self._get(
            "https://api.binance.com/api/v3/ticker/24hr"
        )

        if not isinstance(data, list):
            return []

        results = []

        for item in data:

            symbol = str(
                item.get(
                    "symbol",
                    "",
                )
            ).upper()

            if not symbol.endswith("USDT"):
                continue

            if self._is_leveraged(symbol):
                continue

            base = symbol[:-4]

            if not self._is_valid_base(base):
                continue

            try:

                volume = float(
                    item.get(
                        "quoteVolume",
                        0,
                    )
                )

                price = float(
                    item.get(
                        "lastPrice",
                        0,
                    )
                )

            except (
                TypeError,
                ValueError,
            ):

                continue

            if price <= 0:
                continue

            if volume < self.min_quote_volume:
                continue

            results.append(
                {
                    "symbol": symbol,
                    "base": base,
                    "quote": "USDT",
                    "price": price,
                    "quote_volume_24h": volume,
                    "exchange": "binance",
                }
            )

        logger.info(
            "🟡 Binance eligible pairs: %s",
            len(results),
        )

        return results

    # ==========================================================
    # MEXC
    # ==========================================================

    def _mexc(
        self,
    ) -> List[Dict[str, Any]]:

        data = self._get(
            "https://api.mexc.com/api/v3/ticker/24hr"
        )

        if not isinstance(data, list):
            return []

        results = []

        for item in data:

            symbol = str(
                item.get(
                    "symbol",
                    "",
                )
            ).upper()

            if not symbol.endswith("USDT"):
                continue

            if self._is_leveraged(symbol):
                continue

            base = symbol[:-4]

            if not self._is_valid_base(base):
                continue

            try:

                volume = float(
                    item.get(
                        "quoteVolume",
                        0,
                    )
                )

                price = float(
                    item.get(
                        "lastPrice",
                        0,
                    )
                )

            except (
                TypeError,
                ValueError,
            ):

                continue

            if price <= 0:
                continue

            if volume < self.min_quote_volume:
                continue

            results.append(
                {
                    "symbol": symbol,
                    "base": base,
                    "quote": "USDT",
                    "price": price,
                    "quote_volume_24h": volume,
                    "exchange": "mexc",
                }
            )

        logger.info(
            "🟢 MEXC eligible pairs: %s",
            len(results),
        )

        return results

    # ==========================================================
    # KuCoin
    # ==========================================================

    def _kucoin(
        self,
    ) -> List[Dict[str, Any]]:

        data = self._get(
            "https://api.kucoin.com/api/v1/market/allTickers"
        )

        if not isinstance(data, dict):
            return []

        ticker_data = data.get(
            "data",
            {},
        )

        if not isinstance(
            ticker_data,
            dict,
        ):
            return []

        tickers = ticker_data.get(
            "ticker",
            [],
        )

        if not isinstance(tickers, list):
            return []

        results = []

        for item in tickers:

            raw_symbol = str(
                item.get(
                    "symbol",
                    "",
                )
            ).upper()

            if not raw_symbol.endswith("-USDT"):
                continue

            base = raw_symbol.replace(
                "-USDT",
                "",
            )

            if not self._is_valid_base(base):
                continue

            normalized_symbol = (
                f"{base}USDT"
            )

            if self._is_leveraged(
                normalized_symbol
            ):
                continue

            try:

                price = float(
                    item.get(
                        "last",
                        0,
                    )
                )

                volume = float(
                    item.get(
                        "volValue",
                        0,
                    )
                )

            except (
                TypeError,
                ValueError,
            ):

                continue

            if price <= 0:
                continue

            if volume < self.min_quote_volume:
                continue

            results.append(
                {
                    "symbol": normalized_symbol,
                    "base": base,
                    "quote": "USDT",
                    "price": price,
                    "quote_volume_24h": volume,
                    "exchange": "kucoin",
                }
            )

        logger.info(
            "🔵 KuCoin eligible pairs: %s",
            len(results),
        )

        return results

    # ==========================================================
    # Aggregate
    # ==========================================================

    def _aggregate(
        self,
        markets: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:

        grouped: Dict[
            str,
            Dict[str, Any],
        ] = {}

        for market in markets:

            symbol = market.get(
                "symbol"
            )

            if not symbol:
                continue

            if symbol not in grouped:

                grouped[symbol] = {
                    "symbol": symbol,
                    "base": market.get(
                        "base"
                    ),
                    "quote": "USDT",
                    "exchanges": [],
                    "total_volume_24h": 0.0,
                    "exchange_count": 0,
                    "best_price": market.get(
                        "price"
                    ),
                }

            grouped[symbol][
                "exchanges"
            ].append(
                market.get(
                    "exchange"
                )
            )

            grouped[symbol][
                "total_volume_24h"
            ] += float(
                market.get(
                    "quote_volume_24h",
                    0,
                )
                or 0
            )

        return list(
            grouped.values()
        )

    # ==========================================================
    # Balanced Universe
    # ==========================================================

    def _build_balanced_universe(
        self,
        markets: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Create a volume-diversified universe.

        Instead of:

            highest volume → lowest volume

        which causes the first scan batch to contain mostly
        large-cap assets, we create three liquidity tiers:

            HIGH
            MID
            LOWER

        and interleave them.

        This gives lower-cap assets a real opportunity to reach
        ScannerEngine without removing liquidity protection.
        """

        if not markets:
            return []

        ranked = sorted(
            markets,
            key=lambda item: float(
                item.get(
                    "total_volume_24h",
                    0,
                )
                or 0
            ),
            reverse=True,
        )

        ranked = ranked[
            : self.max_coins
        ]

        total = len(ranked)

        if total <= 3:
            return ranked

        high_end = max(
            1,
            int(
                total * 0.50
            ),
        )

        mid_end = max(
            high_end + 1,
            int(
                total * 0.80
            ),
        )

        high = ranked[
            :high_end
        ]

        mid = ranked[
            high_end:mid_end
        ]

        lower = ranked[
            mid_end:
        ]

        result = []

        high_index = 0
        mid_index = 0
        lower_index = 0

        # Approximate 50/30/20 distribution.
        #
        # Repeating pattern:
        #
        # HIGH HIGH
        # MID
        # LOWER
        #
        # This prevents the first 100 coins from being
        # exclusively the highest-volume assets.

        while (
            high_index < len(high)
            or mid_index < len(mid)
            or lower_index < len(lower)
        ):

            for _ in range(2):

                if high_index < len(high):

                    result.append(
                        high[high_index]
                    )

                    high_index += 1

            if mid_index < len(mid):

                result.append(
                    mid[mid_index]
                )

                mid_index += 1

            if lower_index < len(lower):

                result.append(
                    lower[lower_index]
                )

                lower_index += 1

            # If a tier is exhausted, continue using
            # the remaining tiers.

        return result

    # ==========================================================
    # Public Universe Builder
    # ==========================================================

    def build_universe(
        self,
    ) -> List[Dict[str, Any]]:

        logger.info(
            "🌎 Building broad USDT universe | "
            "min_volume=$%.0f | max_coins=%s",
            self.min_quote_volume,
            self.max_coins,
        )

        all_markets = []

        all_markets.extend(
            self._binance()
        )

        all_markets.extend(
            self._mexc()
        )

        all_markets.extend(
            self._kucoin()
        )

        if not all_markets:

            logger.warning(
                "⚠️ No exchange market data available"
            )

            return []

        aggregated = self._aggregate(
            all_markets
        )

        logger.info(
            "🌐 Aggregated unique symbols: %s",
            len(aggregated),
        )

        universe = (
            self._build_balanced_universe(
                aggregated
            )
        )

        logger.info(
            "🌎 Final balanced universe: %s",
            len(universe),
        )

        return universe

    # ==========================================================
    # Summary
    # ==========================================================

    def summary(
        self,
        universe: List[
            Dict[str, Any]
        ],
    ) -> Dict[str, Any]:

        exchange_count: Dict[
            str,
            int,
        ] = {}

        for item in universe:

            for exchange in item.get(
                "exchanges",
                [],
            ):

                exchange_count[
                    exchange
                ] = (
                    exchange_count.get(
                        exchange,
                        0,
                    )
                    + 1
                )

        return {
            "status": "SUCCESS",
            "total_symbols": len(
                universe
            ),
            "exchange_coverage": (
                exchange_count
            ),
        }
