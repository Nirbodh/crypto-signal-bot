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

    def __init__(self):
        self.exchanges = {}

        exchange_configs = {
            "binance": ccxt.binance({
                "enableRateLimit": True,
            }),
            "mexc": ccxt.mexc({
                "enableRateLimit": True,
            }),
            "kucoin": ccxt.kucoin({
                "enableRateLimit": True,
            }),
        }

        for name, exchange in exchange_configs.items():
            self.exchanges[name] = exchange

    def load_markets(self) -> Dict[str, int]:
        """
        Load markets from all exchanges.

        Returns:
            Dictionary containing number of markets per exchange.
        """

        result = {}

        for name, exchange in self.exchanges.items():
            try:
                markets = exchange.load_markets()
                result[name] = len(markets)

                logger.info(
                    "✅ %s markets loaded: %s",
                    name,
                    len(markets),
                )

            except Exception as exc:
                logger.error(
                    "❌ Failed loading %s markets: %s",
                    name,
                    exc,
                )
                result[name] = 0

        return result

    def get_usdt_symbols(
        self,
        exchange_name: str,
    ) -> List[str]:
        """
        Return active USDT spot symbols.
        """

        exchange = self.exchanges.get(exchange_name)

        if exchange is None:
            return []

        try:
            markets = exchange.load_markets()

            symbols = []

            for symbol, market in markets.items():
                if (
                    market.get("active", True)
                    and market.get("spot", False)
                    and market.get("quote") == "USDT"
                ):
                    symbols.append(symbol)

            return sorted(symbols)

        except Exception as exc:
            logger.error(
                "❌ Failed getting USDT symbols from %s: %s",
                exchange_name,
                exc,
            )
            return []

    def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str = "15m",
        limit: int = 250,
        preferred_exchange: str = "binance",
    ) -> Optional[pd.DataFrame]:
        """
        Fetch OHLCV data.

        Columns:
        timestamp, open, high, low, close, volume
        """

        exchange = self.exchanges.get(preferred_exchange)

        if exchange is None:
            logger.error(
                "Unknown exchange: %s",
                preferred_exchange,
            )
            return None

        try:
            ohlcv = exchange.fetch_ohlcv(
                symbol,
                timeframe=timeframe,
                limit=limit,
            )

            if not ohlcv:
                return None

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

            df = df.dropna().reset_index(drop=True)

            return df

        except Exception as exc:
            logger.error(
                "❌ OHLCV failed | %s | %s | %s",
                preferred_exchange,
                symbol,
                exc,
            )

            return None

    def get_ticker(
        self,
        symbol: str,
        preferred_exchange: str = "binance",
    ) -> Optional[Dict]:

        exchange = self.exchanges.get(preferred_exchange)

        if exchange is None:
            return None

        try:
            ticker = exchange.fetch_ticker(symbol)

            return {
                "symbol": symbol,
                "last": ticker.get("last"),
                "bid": ticker.get("bid"),
                "ask": ticker.get("ask"),
                "base_volume": ticker.get("baseVolume"),
                "quote_volume": ticker.get("quoteVolume"),
                "timestamp": ticker.get("timestamp"),
            }

        except Exception as exc:
            logger.error(
                "❌ Ticker failed | %s | %s | %s",
                preferred_exchange,
                symbol,
                exc,
            )

            return None        self,
        symbol: str,
        timeframe: str = "15m",
        limit: int = 250,
        preferred_exchange: str = "binance",
    ) -> Optional[pd.DataFrame]:
        """
        Fetch OHLCV data.

        Columns:
        timestamp, open, high, low, close, volume
        """

        exchange = self.exchanges.get(preferred_exchange)

        if exchange is None:
            logger.error(
                "Unknown exchange: %s",
                preferred_exchange,
            )
            return None

        try:
            ohlcv = exchange.fetch_ohlcv(
                symbol,
                timeframe=timeframe,
                limit=limit,
            )

            if not ohlcv:
                return None

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

            df = df.dropna().reset_index(drop=True)

            return df

        except Exception as exc:
            logger.error(
                "❌ OHLCV failed | %s | %s | %s",
                preferred_exchange,
                symbol,
                exc,
            )

            return None

    def get_ticker(
        self,
        symbol: str,
        preferred_exchange: str = "binance",
    ) -> Optional[Dict]:

        exchange = self.exchanges.get(preferred_exchange)

        if exchange is None:
            return None

        try:
            ticker = exchange.fetch_ticker(symbol)

            return {
                "symbol": symbol,
                "last": ticker.get("last"),
                "bid": ticker.get("bid"),
                "ask": ticker.get("ask"),
                "base_volume": ticker.get("baseVolume"),
                "quote_volume": ticker.get("quoteVolume"),
                "timestamp": ticker.get("timestamp"),
            }

        except Exception as exc:
            logger.error(
                "❌ Ticker failed | %s | %s | %s",
                preferred_exchange,
                symbol,
                exc,
            )b

            return None
