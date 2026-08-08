import logging
from typing import Dict, List, Optional

import ccxt
import pandas as pd


logger = logging.getLogger("crypto-signal-bot")


class MarketDataEngine:
    """
    Public market-data engine.

    Exchanges:
        - Binance
        - MEXC
        - KuCoin

    No private API keys are required.
    """

    def __init__(self) -> None:

        self.exchanges: Dict[str, ccxt.Exchange] = {}

        configs = {
            "binance": ccxt.binance,
            "mexc": ccxt.mexc,
            "kucoin": ccxt.kucoin,
        }

        for name, exchange_class in configs.items():

            try:
                self.exchanges[name] = exchange_class(
                    {
                        "enableRateLimit": True,
                    }
                )

                logger.info(
                    "Exchange initialized: %s",
                    name,
                )

            except Exception as exc:

                logger.error(
                    "Failed to initialize %s: %s",
                    name,
                    exc,
                )

    # ======================================================
    # Load Markets
    # ======================================================

    def load_markets(self) -> Dict[str, int]:

        result: Dict[str, int] = {}

        for name, exchange in self.exchanges.items():

            try:

                markets = exchange.load_markets()

                result[name] = len(markets)

                logger.info(
                    "Markets loaded | %s | %s",
                    name,
                    len(markets),
                )

            except Exception as exc:

                logger.error(
                    "Market loading failed | %s | %s",
                    name,
                    exc,
                )

                result[name] = 0

        return result

    # ======================================================
    # USDT Symbols
    # ======================================================

    def get_usdt_symbols(
        self,
        exchange_name: str,
    ) -> List[str]:

        exchange = self.exchanges.get(
            exchange_name
        )

        if exchange is None:

            logger.warning(
                "Unknown exchange: %s",
                exchange_name,
            )

            return []

        try:

            markets = exchange.load_markets()

            symbols: List[str] = []

            for symbol, market in markets.items():

                if not market.get(
                    "active",
                    True,
                ):
                    continue

                if not market.get(
                    "spot",
                    False,
                ):
                    continue

                if market.get(
                    "quote"
                ) != "USDT":
                    continue

                symbols.append(symbol)

            return sorted(symbols)

        except Exception as exc:

            logger.error(
                "USDT symbol loading failed | %s | %s",
                exchange_name,
                exc,
            )

            return []

    # ======================================================
    # Exchange Order
    # ======================================================

    def _exchange_order(
        self,
        preferred_exchange: str,
    ) -> List[str]:

        default_order = [
            "binance",
            "mexc",
            "kucoin",
        ]

        order: List[str] = []

        if preferred_exchange in self.exchanges:

            order.append(
                preferred_exchange
            )

        for name in default_order:

            if name not in order:

                if name in self.exchanges:

                    order.append(name)

        return order

    # ======================================================
    # OHLCV
    # ======================================================

    def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str = "15m",
        limit: int = 250,
        preferred_exchange: str = "binance",
    ) -> Optional[pd.DataFrame]:

        exchanges = self._exchange_order(
            preferred_exchange
        )

        for exchange_name in exchanges:

            exchange = self.exchanges.get(
                exchange_name
            )

            if exchange is None:
                continue

            try:

                if not exchange.markets:

                    exchange.load_markets()

                if symbol not in exchange.markets:

                    logger.debug(
                        "Symbol unavailable | %s | %s",
                        exchange_name,
                        symbol,
                    )

                    continue

                if not exchange.has.get(
                    "fetchOHLCV",
                    False,
                ):

                    continue

                ohlcv = exchange.fetch_ohlcv(
                    symbol,
                    timeframe=timeframe,
                    limit=limit,
                )

                if not ohlcv:

                    continue

                df = pd.DataFrame(
                    ohlcv,
                    columns=[
                        "timestamp",
                        "open",
                        "high",
                        "low",
                        "close",
                        "volume",
                    ],
                )

                df["timestamp"] = pd.to_datetime(
                    df["timestamp"],
                    unit="ms",
                    utc=True,
                )

                numeric_columns = [
                    "open",
                    "high",
                    "low",
                    "close",
                    "volume",
                ]

                for column in numeric_columns:

                    df[column] = pd.to_numeric(
                        df[column],
                        errors="coerce",
                    )

                df = df.dropna()

                df = df.drop_duplicates(
                    subset=["timestamp"]
                )

                df = df.sort_values(
                    "timestamp"
                )

                df = df.reset_index(
                    drop=True
                )

                if df.empty:

                    continue

                logger.debug(
                    "OHLCV success | %s | %s | %s | rows=%s",
                    exchange_name,
                    symbol,
                    timeframe,
                    len(df),
                )

                return df

            except Exception as exc:

                logger.warning(
                    "OHLCV failed | %s | %s | %s",
                    exchange_name,
                    symbol,
                    exc,
                )

        logger.error(
            "OHLCV unavailable on all exchanges | %s | %s",
            symbol,
            timeframe,
        )

        return None

    # ======================================================
    # Ticker
    # ======================================================

    def get_ticker(
        self,
        symbol: str,
        preferred_exchange: str = "binance",
    ) -> Optional[Dict]:

        exchanges = self._exchange_order(
            preferred_exchange
        )

        for exchange_name in exchanges:

            exchange = self.exchanges.get(
                exchange_name
            )

            if exchange is None:
                continue

            try:

                if not exchange.markets:

                    exchange.load_markets()

                if symbol not in exchange.markets:

                    continue

                ticker = exchange.fetch_ticker(
                    symbol
                )

                if not ticker:

                    continue

                return {
                    "symbol": symbol,
                    "last": ticker.get("last"),
                    "bid": ticker.get("bid"),
                    "ask": ticker.get("ask"),
                    "base_volume": ticker.get(
                        "baseVolume"
                    ),
                    "quote_volume": ticker.get(
                        "quoteVolume"
                    ),
                    "timestamp": ticker.get(
                        "timestamp"
                    ),
                    "exchange": exchange_name,
                }

            except Exception as exc:

                logger.warning(
                    "Ticker failed | %s | %s | %s",
                    exchange_name,
                    symbol,
                    exc,
                )

        logger.error(
            "Ticker unavailable on all exchanges | %s",
            symbol,
        )

        return None

    # ======================================================
    # Exchange Status
    # ======================================================

    def get_exchange_status(
        self,
    ) -> Dict[str, bool]:

        return {
            name: True
            for name in self.exchanges
        }
