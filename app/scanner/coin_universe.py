import logging
from typing import Any, Dict, List, Set

import requests


logger = logging.getLogger("crypto-signal-bot")


class CoinUniverseEngine:
    """
    Builds a clean USDT trading universe using public
    exchange market endpoints.

    Exchanges:
        Binance
        MEXC
        KuCoin

    No exchange API keys are required.
    """

    def __init__(
        self,
        timeout: int = 10,
        min_quote_volume: float = 1_000_000,
        max_coins: int = 300,
    ):

        self.timeout = timeout

        self.min_quote_volume = (
            min_quote_volume
        )

        self.max_coins = max_coins

        self.session = requests.Session()

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
                "Public API request failed: %s",
                exc,
            )

            return None

    # ==========================================================
    # Binance
    # ==========================================================

    def _binance(
        self,
    ) -> List[Dict[str, Any]]:

        url = (
            "https://api.binance.com"
            "/api/v3/ticker/24hr"
        )

        data = self._get(
            url
        )

        if not isinstance(
            data,
            list,
        ):

            return []

        results = []

        for item in data:

            symbol = item.get(
                "symbol",
                "",
            )

            if not symbol.endswith(
                "USDT"
            ):

                continue

            # Exclude leveraged tokens.

            if any(
                token in symbol
                for token in (
                    "UPUSDT",
                    "DOWNUSDT",
                    "BULLUSDT",
                    "BEARUSDT",
                )
            ):

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

            if (
                price <= 0
                or volume < self.min_quote_volume
            ):

                continue

            results.append(
                {
                    "symbol": symbol,
                    "base": symbol[
                        :-4
                    ],
                    "quote": "USDT",
                    "price": price,
                    "quote_volume_24h": volume,
                    "exchange": "binance",
                }
            )

        return results

    # ==========================================================
    # MEXC
    # ==========================================================

    def _mexc(
        self,
    ) -> List[Dict[str, Any]]:

        url = (
            "https://api.mexc.com"
            "/api/v3/ticker/24hr"
        )

        data = self._get(
            url
        )

        if not isinstance(
            data,
            list,
        ):

            return []

        results = []

        for item in data:

            symbol = item.get(
                "symbol",
                "",
            )

            if not symbol.endswith(
                "USDT"
            ):

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

            if (
                price <= 0
                or volume < self.min_quote_volume
            ):

                continue

            results.append(
                {
                    "symbol": symbol,
                    "base": symbol[
                        :-4
                    ],
                    "quote": "USDT",
                    "price": price,
                    "quote_volume_24h": volume,
                    "exchange": "mexc",
                }
            )

        return results

    # ==========================================================
    # KuCoin
    # ==========================================================

    def _kucoin(
        self,
    ) -> List[Dict[str, Any]]:

        url = (
            "https://api.kucoin.com"
            "/api/v1/market/allTickers"
        )

        data = self._get(
            url
        )

        if not isinstance(
            data,
            dict,
        ):

            return []

        ticker_data = data.get(
            "data",
            {},
        )

        tickers = ticker_data.get(
            "ticker",
            [],
        )

        if not isinstance(
            tickers,
            list,
        ):

            return []

        results = []

        for item in tickers:

            symbol = item.get(
                "symbol",
                "",
            )

            if not symbol.endswith(
                "-USDT"
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

            if (
                price <= 0
                or volume < self.min_quote_volume
            ):

                continue

            base = symbol.replace(
                "-USDT",
                "",
            )

            results.append(
                {
                    "symbol": (
                        f"{base}USDT"
                    ),
                    "base": base,
                    "quote": "USDT",
                    "price": price,
                    "quote_volume_24h": volume,
                    "exchange": "kucoin",
                }
            )

        return results

    # ==========================================================
    # Merge
    # ==========================================================

    def build_universe(
        self,
    ) -> List[Dict[str, Any]]:

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

        # ------------------------------------------------------
        # Aggregate by symbol
        # ------------------------------------------------------

        grouped: Dict[
            str,
            Dict[str, Any],
        ] = {}

        for market in all_markets:

            symbol = market[
                "symbol"
            ]

            if symbol not in grouped:

                grouped[symbol] = {
                    "symbol": symbol,
                    "base": market[
                        "base"
                    ],
                    "quote": "USDT",
                    "exchanges": [],
                    "total_volume_24h": 0.0,
                    "best_price": market[
                        "price"
                    ],
                }

            grouped[
                symbol
            ][
                "exchanges"
            ].append(
                market[
                    "exchange"
                ]
            )

            grouped[
                symbol
            ][
                "total_volume_24h"
            ] += market[
                "quote_volume_24h"
            ]

        # ------------------------------------------------------
        # Sort by total liquidity
        # ------------------------------------------------------

        universe = sorted(
            grouped.values(),
            key=lambda x: x[
                "total_volume_24h"
            ],
            reverse=True,
        )

        # ------------------------------------------------------
        # Limit
        # ------------------------------------------------------

        universe = universe[
            : self.max_coins
        ]

        return universe

    # ==========================================================
    # Simple summary
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

            for exchange in item[
                "exchanges"
            ]:

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
