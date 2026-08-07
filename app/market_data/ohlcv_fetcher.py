import logging
from typing import Any, Dict, List, Optional

import requests
import pandas as pd


logger = logging.getLogger("crypto-signal-bot")


class OHLCVFetcher:
    """
    Public OHLCV market data fetcher.

    Sources:
        Binance
        MEXC
        KuCoin

    No API keys required.
    """

    def __init__(
        self,
        timeout: int = 10,
    ):

        self.timeout = timeout

        self.session = requests.Session()


    # ==========================================================
    # HTTP
    # ==========================================================

    def _get(
        self,
        url: str,
        params: Dict[str, Any],
    ) -> Optional[Any]:

        try:

            response = self.session.get(
                url,
                params=params,
                timeout=self.timeout,
            )

            response.raise_for_status()

            return response.json()

        except requests.RequestException as exc:

            logger.warning(
                "OHLCV request failed: %s",
                exc,
            )

            return None


    # ==========================================================
    # Binance
    # ==========================================================

    def _binance(
        self,
        symbol: str,
        timeframe: str,
        limit: int,
    ) -> List[List]:

        url = (
            "https://api.binance.com"
            "/api/v3/klines"
        )

        params = {

            "symbol": symbol,

            "interval": timeframe,

            "limit": limit,
        }

        data = self._get(
            url,
            params,
        )

        if not isinstance(
            data,
            list,
        ):

            return []

        candles = []

        for item in data:

            candles.append(
                [
                    item[0],      # time
                    item[1],      # open
                    item[2],      # high
                    item[3],      # low
                    item[4],      # close
                    item[5],      # volume
                ]
            )

        return candles


    # ==========================================================
    # MEXC
    # ==========================================================

    def _mexc(
        self,
        symbol: str,
        timeframe: str,
        limit: int,
    ) -> List[List]:

        url = (
            "https://api.mexc.com"
            "/api/v3/klines"
        )

        params = {

            "symbol": symbol,

            "interval": timeframe,

            "limit": limit,
        }

        data = self._get(
            url,
            params,
        )

        if not isinstance(
            data,
            list,
        ):

            return []

        candles = []

        for item in data:

            candles.append(
                [
                    item[0],
                    item[1],
                    item[2],
                    item[3],
                    item[4],
                    item[5],
                ]
            )

        return candles


    # ==========================================================
    # KuCoin
    # ==========================================================

    def _kucoin(
        self,
        symbol: str,
        timeframe: str,
        limit: int,
    ) -> List[List]:

        # KuCoin uses minutes.

        interval_map = {

            "1m": "1",

            "5m": "5",

            "15m": "15",

            "30m": "30",

            "1h": "60",

            "4h": "240",

            "1d": "1440",
        }


        interval = interval_map.get(
            timeframe,
            "15",
        )


        url = (
            "https://api.kucoin.com"
            "/api/v1/market/candles"
        )


        params = {

            "symbol": (
                symbol.replace(
                    "USDT",
                    "-USDT",
                )
            ),

            "type": interval,

        }


        data = self._get(
            url,
            params,
        )


        if not isinstance(
            data,
            dict,
        ):

            return []


        candles_raw = (
            data
            .get(
                "data",
                [],
            )
        )


        candles = []


        for item in candles_raw[:limit]:

            # KuCoin:
            # time, open, close,
            # high, low, volume,...

            candles.append(
                [
                    int(
                        float(
                            item[0]
                        )
                        * 1000
                    ),

                    item[1],

                    item[3],

                    item[4],

                    item[2],

                    item[5],
                ]
            )


        return candles



    # ==========================================================
    # Public fetch
    # ==========================================================

    def fetch(
        self,
        symbol: str,
        timeframe: str = "15m",
        limit: int = 200,
    ) -> pd.DataFrame:


        sources = [

            (
                "binance",
                self._binance,
            ),

            (
                "mexc",
                self._mexc,
            ),

            (
                "kucoin",
                self._kucoin,
            ),

        ]


        candles = []


        for name, func in sources:

            try:

                candles = func(
                    symbol,
                    timeframe,
                    limit,
                )


                if candles:

                    logger.info(
                        "OHLCV source: %s",
                        name,
                    )

                    break


            except Exception as exc:

                logger.warning(
                    "%s failed: %s",
                    name,
                    exc,
                )


        if not candles:

            return pd.DataFrame()


        df = pd.DataFrame(
            candles,
            columns=[
                "timestamp",
                "open",
                "high",
                "low",
                "close",
                "volume",
            ],
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


        df["timestamp"] = pd.to_datetime(
            df["timestamp"],
            unit="ms",
        )


        df = df.sort_values(
            "timestamp"
        )


        df.reset_index(
            drop=True,
            inplace=True,
        )


        return df
