import logging
import time

from app.config import Config
from app.data.market_data import MarketDataEngine
from app.universe.coin_universe import CoinUniverseEngine
from app.universe.liquidity_ranker import LiquidityRanker


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

logger = logging.getLogger("crypto-signal-bot")


def run():

    logger.info("🚀 Crypto Signal Bot started")

    # ==================================================
    # MARKET DATA
    # ==================================================

    market_data = MarketDataEngine()

    logger.info(
        "📡 Loading exchange markets..."
    )

    market_status = (
        market_data.load_markets()
    )

    logger.info(
        "Exchange status: %s",
        market_status,
    )

    # ==================================================
    # COIN UNIVERSE
    # ==================================================

    universe_engine = CoinUniverseEngine(
        market_data
    )

    symbols = (
        universe_engine
        .build_cross_exchange_universe()
    )

    logger.info(
        "🪙 Clean USDT universe: %s",
        len(symbols),
    )

    # ==================================================
    # LIQUIDITY RANKING
    # ==================================================

    liquidity_ranker = LiquidityRanker(
        market_data
    )

    ranked = (
        liquidity_ranker
        .build_ranked_universe(
            minimum_volume=1_000_000,
            maximum_coins=250,
        )
    )

    if ranked.empty:

        logger.error(
            "❌ No liquid coins available."
        )

    else:

        logger.info(
            "🏆 Top liquid coins:"
        )

        logger.info(
            "\n%s",
            ranked[
                [
                    "base",
                    "total_volume_24h",
                    "exchange_count",
                    "liquidity_score",
                ]
            ]
            .head(20)
            .to_string(index=False),
        )

    # ==================================================
    # TEST OHLCV
    # ==================================================

    df = market_data.fetch_ohlcv(
        symbol="BTC/USDT",
        timeframe="15m",
        limit=100,
        preferred_exchange="binance",
    )

    if df is not None and not df.empty:

        logger.info(
            "✅ BTC/USDT OHLCV: %s candles",
            len(df),
        )

    else:

        logger.error(
            "❌ BTC/USDT OHLCV failed."
        )

    logger.info(
        "🧪 Step 5 liquidity test completed."
    )

    # Temporary runtime loop
    while True:

        time.sleep(
            Config.SCAN_INTERVAL_MINUTES
            * 60
        )


if __name__ == "__main__":
    run()
