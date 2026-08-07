import logging
import time

from app.config import Config
from app.data.market_data import MarketDataEngine


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

logger = logging.getLogger("crypto-signal-bot")


def run():
    logger.info("🚀 Crypto Signal Bot started")

    market_data = MarketDataEngine()

    logger.info("📡 Loading exchange markets...")

    market_status = market_data.load_markets()

    logger.info(
        "Exchange status: %s",
        market_status,
    )

    # Test Binance symbols
    symbols = market_data.get_usdt_symbols("binance")

    logger.info(
        "Binance USDT spot pairs: %s",
        len(symbols),
    )

    # Test one liquid pair
    test_symbol = "BTC/USDT"

    df = market_data.fetch_ohlcv(
        symbol=test_symbol,
        timeframe="15m",
        limit=100,
        preferred_exchange="binance",
    )

    if df is not None and not df.empty:
        logger.info(
            "✅ %s OHLCV loaded: %s candles",
            test_symbol,
            len(df),
        )

        logger.info(
            "Latest candle:\n%s",
            df.tail(1).to_string(index=False),
        )

    else:
        logger.error(
            "❌ Could not fetch %s data",
            test_symbol,
        )

    logger.info("🧪 Step 3 market-data test completed")

    # Temporary loop.
    # Later this will become the real scheduler.
    while True:
        time.sleep(
            Config.SCAN_INTERVAL_MINUTES * 60
        )


if __name__ == "__main__":
    run()
