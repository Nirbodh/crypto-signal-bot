import logging
import os
from typing import Any, Dict, Optional

import requests


logger = logging.getLogger("crypto-signal-bot")


class MarketContextEngine:
    """
    Collects broader market/fundamental context.

    This engine is intentionally non-blocking:
    if one provider fails, the whole analysis should continue.

    It does NOT generate BUY/SELL signals.
    """

    def __init__(
        self,
        timeout: int = 10,
    ):
        self.timeout = timeout

        self.coinmarketcap_key = os.getenv(
            "COINMARKETCAP_API_KEY"
        )

        self.cryptocompare_key = os.getenv(
            "CRYPTOCOMPARE_API_KEY"
        )

        self.coingecko_key = os.getenv(
            "COINGECKO_API_KEY"
        )

        self.coinglass_key = os.getenv(
            "COINGLASS_API_KEY"
        )

    # ==========================================================
    # HTTP helper
    # ==========================================================

    def _get(
        self,
        url: str,
        headers: Optional[
            Dict[str, str]
        ] = None,
        params: Optional[
            Dict[str, Any]
        ] = None,
    ) -> Optional[Dict[str, Any]]:

        try:

            response = requests.get(
                url,
                headers=headers or {},
                params=params or {},
                timeout=self.timeout,
            )

            response.raise_for_status()

            return response.json()

        except requests.RequestException as exc:

            logger.warning(
                "Market API request failed: %s",
                exc,
            )

        except ValueError as exc:

            logger.warning(
                "Invalid JSON response: %s",
                exc,
            )

        return None

    # ==========================================================
    # CoinMarketCap
    # ==========================================================

    def get_coinmarketcap(
        self,
        symbol: str,
    ) -> Dict[str, Any]:

        if not self.coinmarketcap_key:

            return {
                "provider": "coinmarketcap",
                "status": "SKIPPED",
                "reason": "API key not configured",
            }

        url = (
            "https://pro-api.coinmarketcap.com"
            "/v1/cryptocurrency/quotes/latest"
        )

        headers = {
            "X-CMC_PRO_API_KEY": (
                self.coinmarketcap_key
            )
        }

        params = {
            "symbol": symbol.upper(),
            "convert": "USD",
        }

        data = self._get(
            url,
            headers=headers,
            params=params,
        )

        if not data:

            return {
                "provider": "coinmarketcap",
                "status": "FAILED",
            }

        try:

            coin = data[
                "data"
            ][symbol.upper()]

            quote = coin[
                "quote"
            ]["USD"]

            return {
                "provider": "coinmarketcap",
                "status": "SUCCESS",
                "market_cap": quote.get(
                    "market_cap"
                ),
                "volume_24h": quote.get(
                    "volume_24h"
                ),
                "percent_change_24h": quote.get(
                    "percent_change_24h"
                ),
                "circulating_supply": coin.get(
                    "circulating_supply"
                ),
                "total_supply": coin.get(
                    "total_supply"
                ),
                "max_supply": coin.get(
                    "max_supply"
                ),
            }

        except (
            KeyError,
            TypeError,
        ):

            return {
                "provider": "coinmarketcap",
                "status": "PARSE_ERROR",
            }

    # ==========================================================
    # CoinGecko
    # ==========================================================

    def get_coingecko(
        self,
        coin_id: str,
    ) -> Dict[str, Any]:

        url = (
            "https://api.coingecko.com"
            "/api/v3/coins/"
            f"{coin_id}"
        )

        headers = {}

        if self.coingecko_key:

            headers[
                "x-cg-demo-api-key"
            ] = self.coingecko_key

        data = self._get(
            url,
            headers=headers,
        )

        if not data:

            return {
                "provider": "coingecko",
                "status": "FAILED",
            }

        market = data.get(
            "market_data",
            {},
        )

        return {
            "provider": "coingecko",
            "status": "SUCCESS",
            "market_cap": (
                market
                .get("market_cap", {})
                .get("usd")
            ),
            "volume_24h": (
                market
                .get("total_volume", {})
                .get("usd")
            ),
            "price_change_24h": (
                market
                .get(
                    "price_change_percentage_24h"
                )
            ),
            "market_cap_rank": data.get(
                "market_cap_rank"
            ),
            "circulating_supply": (
                market.get(
                    "circulating_supply"
                )
            ),
            "total_supply": (
                market.get(
                    "total_supply"
                )
            ),
            "max_supply": (
                market.get(
                    "max_supply"
                )
            ),
        }

    # ==========================================================
    # CryptoCompare
    # ==========================================================

    def get_cryptocompare(
        self,
        symbol: str,
    ) -> Dict[str, Any]:

        url = (
            "https://min-api.cryptocompare.com"
            "/data/pricemultifull"
        )

        params = {
            "fsyms": symbol.upper(),
            "tsyms": "USD",
        }

        headers = {}

        if self.cryptocompare_key:

            headers[
                "authorization"
            ] = (
                "Apikey "
                + self.cryptocompare_key
            )

        data = self._get(
            url,
            headers=headers,
            params=params,
        )

        if not data:

            return {
                "provider": "cryptocompare",
                "status": "FAILED",
            }

        try:

            raw = data[
                "RAW"
            ][symbol.upper()]["USD"]

            return {
                "provider": "cryptocompare",
                "status": "SUCCESS",
                "price": raw.get(
                    "PRICE"
                ),
                "volume_24h": raw.get(
                    "VOLUME24HOUR"
                ),
                "market_cap": raw.get(
                    "MKTCAP"
                ),
                "change_24h": raw.get(
                    "CHANGEPCT24HOUR"
                ),
            }

        except (
            KeyError,
            TypeError,
        ):

            return {
                "provider": "cryptocompare",
                "status": "PARSE_ERROR",
            }

    # ==========================================================
    # Provider comparison
    # ==========================================================

    def compare_market_data(
        self,
        cmc: Dict[str, Any],
        gecko: Dict[str, Any],
        cryptocompare: Dict[str, Any],
    ) -> Dict[str, Any]:

        market_caps = []

        volumes = []

        for source in (
            cmc,
            gecko,
            cryptocompare,
        ):

            if source.get(
                "status"
            ) != "SUCCESS":

                continue

            market_cap = source.get(
                "market_cap"
            )

            volume = source.get(
                "volume_24h"
            )

            if (
                isinstance(
                    market_cap,
                    (int, float),
                )
                and market_cap > 0
            ):

                market_caps.append(
                    float(market_cap)
                )

            if (
                isinstance(
                    volume,
                    (int, float),
                )
                and volume > 0
            ):

                volumes.append(
                    float(volume)
                )

        result = {
            "market_cap_consensus": None,
            "volume_consensus": None,
            "market_cap_spread_pct": None,
            "volume_spread_pct": None,
        }

        if market_caps:

            result[
                "market_cap_consensus"
            ] = sum(
                market_caps
            ) / len(market_caps)

            if len(market_caps) > 1:

                minimum = min(
                    market_caps
                )

                maximum = max(
                    market_caps
                )

                if minimum > 0:

                    result[
                        "market_cap_spread_pct"
                    ] = (
                        (
                            maximum
                            - minimum
                        )
                        / minimum
                    ) * 100

        if volumes:

            result[
                "volume_consensus"
            ] = sum(
                volumes
            ) / len(volumes)

            if len(volumes) > 1:

                minimum = min(
                    volumes
                )

                maximum = max(
                    volumes
                )

                if minimum > 0:

                    result[
                        "volume_spread_pct"
                    ] = (
                        (
                            maximum
                            - minimum
                        )
                        / minimum
                    ) * 100

        return result

    # ==========================================================
    # Fundamental context
    # ==========================================================

    def build_fundamental_context(
        self,
        cmc: Dict[str, Any],
        gecko: Dict[str, Any],
        cryptocompare: Dict[str, Any],
    ) -> Dict[str, Any]:

        market_caps = []

        market_ranks = []

        circulating_supply = []

        total_supply = []

        max_supply = []

        changes_24h = []

        for source in (
            cmc,
            gecko,
            cryptocompare,
        ):

            if source.get(
                "status"
            ) != "SUCCESS":

                continue

            if isinstance(
                source.get(
                    "market_cap"
                ),
                (int, float),
            ):

                market_caps.append(
                    float(
                        source[
                            "market_cap"
                        ]
                    )
                )

            if isinstance(
                source.get(
                    "market_cap_rank"
                ),
                int,
            ):

                market_ranks.append(
                    source[
                        "market_cap_rank"
                    ]
                )

            if isinstance(
                source.get(
                    "circulating_supply"
                ),
                (int, float),
            ):

                circulating_supply.append(
                    float(
                        source[
                            "circulating_supply"
                        ]
                    )
                )

            if isinstance(
                source.get(
                    "total_supply"
                ),
                (int, float),
            ):

                total_supply.append(
                    float(
                        source[
                            "total_supply"
                        ]
                    )
                )

            if isinstance(
                source.get(
                    "max_supply"
                ),
                (int, float),
            ):

                max_supply.append(
                    float(
                        source[
                            "max_supply"
                        ]
                    )
                )

            change = source.get(
                "percent_change_24h"
            )

            if change is None:

                change = source.get(
                    "change_24h"
                )

            if isinstance(
                change,
                (int, float),
            ):

                changes_24h.append(
                    float(change)
                )

        context = {
            "market_cap": (
                sum(market_caps)
                / len(market_caps)
                if market_caps
                else None
            ),

            "market_cap_rank": (
                min(market_ranks)
                if market_ranks
                else None
            ),

            "circulating_supply": (
                sum(circulating_supply)
                / len(
                    circulating_supply
                )
                if circulating_supply
                else None
            ),

            "total_supply": (
                sum(total_supply)
                / len(total_supply)
                if total_supply
                else None
            ),

            "max_supply": (
                sum(max_supply)
                / len(max_supply)
                if max_supply
                else None
            ),

            "change_24h": (
                sum(changes_24h)
                / len(changes_24h)
                if changes_24h
                else None
            ),
        }

        # ------------------------------------------------------
        # Supply pressure indicator
        # ------------------------------------------------------

        if (
            context["max_supply"]
            and context[
                "circulating_supply"
            ]
        ):

            context[
                "circulating_ratio"
            ] = (
                context[
                    "circulating_supply"
                ]
                / context[
                    "max_supply"
                ]
            )

        else:

            context[
                "circulating_ratio"
            ] = None

        return context

    # ==========================================================
    # Main
    # ==========================================================

    def analyze(
        self,
        symbol: str,
        coin_id: Optional[str] = None,
    ) -> Dict[str, Any]:

        # CoinMarketCap
        cmc = self.get_coinmarketcap(
            symbol
        )

        # CoinGecko
        if coin_id:

            gecko = self.get_coingecko(
                coin_id
            )

        else:

            gecko = {
                "provider": "coingecko",
                "status": "SKIPPED",
                "reason": (
                    "coin_id not supplied"
                ),
            }

        # CryptoCompare
        cryptocompare = (
            self.get_cryptocompare(
                symbol
            )
        )

        comparison = (
            self.compare_market_data(
                cmc,
                gecko,
                cryptocompare,
            )
        )

        fundamental = (
            self.build_fundamental_context(
                cmc,
                gecko,
                cryptocompare,
            )
        )

        return {
            "symbol": symbol.upper(),

            "providers": {
                "coinmarketcap": cmc,
                "coingecko": gecko,
                "cryptocompare": (
                    cryptocompare
                ),
            },

            "comparison": comparison,

            "fundamental": fundamental,

            "status": "SUCCESS",
        }
