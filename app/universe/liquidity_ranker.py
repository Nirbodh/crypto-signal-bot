import logging
from typing import Dict, List

import pandas as pd

from app.data.market_data import MarketDataEngine


logger = logging.getLogger("crypto-signal-bot")


class LiquidityRanker:
    """
    Ranks crypto assets by market liquidity and activity.

    This is NOT a trading signal engine.
    It only selects assets that deserve deeper analysis.
    """

    def __init__(
        self,
        market_data: MarketDataEngine,
    ):
        self.market_data = market_data

    def fetch_exchange_tickers(
        self,
        exchange_name: str,
    ) -> List[Dict]:

        exchange = self.market_data.exchanges.get(
            exchange_name
        )

        if exchange is None:
            return []

        try:
            tickers = exchange.fetch_tickers()

            results = []

            for symbol, ticker in tickers.items():

                if not symbol.endswith("/USDT"):
                    continue

                base = symbol.split("/")[0]

                quote_volume = ticker.get(
                    "quoteVolume"
                )

                last_price = ticker.get("last")

                if quote_volume is None:
                    continue

                try:
                    quote_volume = float(
                        quote_volume
                    )
                except (TypeError, ValueError):
                    continue

                if quote_volume <= 0:
                    continue

                results.append({
                    "exchange": exchange_name,
                    "symbol": symbol,
                    "base": base,
                    "price": last_price,
                    "quote_volume_24h": quote_volume,
                })

            return results

        except Exception as exc:

            logger.error(
                "❌ Failed ticker loading | %s | %s",
                exchange_name,
                exc,
            )

            return []

    def collect_liquidity_data(
        self,
    ) -> List[Dict]:

        all_rows = []

        for exchange_name in [
            "binance",
            "mexc",
            "kucoin",
        ]:

            logger.info(
                "📊 Loading 24h tickers: %s",
                exchange_name,
            )

            rows = self.fetch_exchange_tickers(
                exchange_name
            )

            all_rows.extend(rows)

            logger.info(
                "✅ %s ticker rows: %s",
                exchange_name,
                len(rows),
            )

        return all_rows

    def build_ranked_universe(
        self,
        minimum_volume: float = 1_000_000,
        maximum_coins: int = 250,
    ) -> pd.DataFrame:

        rows = self.collect_liquidity_data()

        if not rows:
            logger.warning(
                "⚠️ No liquidity data received."
            )

            return pd.DataFrame()

        df = pd.DataFrame(rows)

        # --------------------------------------------------
        # Minimum liquidity
        # --------------------------------------------------

        df = df[
            df["quote_volume_24h"]
            >= minimum_volume
        ].copy()

        if df.empty:
            logger.warning(
                "⚠️ No coins passed volume filter."
            )

            return df

        # --------------------------------------------------
        # Aggregate by coin
        # --------------------------------------------------

        grouped = (
            df.groupby("base")
            .agg(
                total_volume_24h=(
                    "quote_volume_24h",
                    "sum",
                ),
                exchange_count=(
                    "exchange",
                    "nunique",
                ),
                average_price=(
                    "price",
                    "mean",
                ),
            )
            .reset_index()
        )

        # --------------------------------------------------
        # Liquidity score
        # --------------------------------------------------

        grouped["volume_score"] = (
            grouped["total_volume_24h"]
            .rank(
                pct=True
            )
            * 70
        )

        grouped["exchange_score"] = (
            grouped["exchange_count"]
            .clip(
                upper=3
            )
            / 3
            * 30
        )

        grouped["liquidity_score"] = (
            grouped["volume_score"]
            + grouped["exchange_score"]
        )

        # --------------------------------------------------
        # Sort
        # --------------------------------------------------

        grouped = grouped.sort_values(
            by=[
                "liquidity_score",
                "total_volume_24h",
            ],
            ascending=False,
        )

        grouped = grouped.head(
            maximum_coins
        )

        grouped = grouped.reset_index(
            drop=True
        )

        logger.info(
            "🏆 Final liquid universe: %s coins",
            len(grouped),
        )

        return grouped
