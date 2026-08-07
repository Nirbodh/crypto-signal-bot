import logging

from app.data.market_data import MarketDataEngine
from app.smc.smc_engine import SMCEngine


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)


def main():

    market_data = MarketDataEngine()

    smc = SMCEngine()

    df = market_data.fetch_ohlcv(
        symbol="BTC/USDT",
        timeframe="15m",
        limit=250,
        preferred_exchange="binance",
    )

    if df is None or df.empty:
        print("❌ Failed to fetch BTC/USDT")
        return

    result = smc.analyze(df)

    if result is None:
        print("❌ SMC analysis failed")
        return

    print("\n========== SMC RESULT ==========\n")

    print(
        f"Structure: "
        f"{result['last_structure']}"
    )

    print(
        f"Swing Highs: "
        f"{result['swing_high_count']}"
    )

    print(
        f"Swing Lows: "
        f"{result['swing_low_count']}"
    )

    print(
        f"BOS/CHoCH Events: "
        f"{result['event_count']}"
    )

    print(
        f"Recent Bullish Sweep: "
        f"{result['recent']['bullish_sweep']}"
    )

    print(
        f"Recent Bearish Sweep: "
        f"{result['recent']['bearish_sweep']}"
    )

    print(
        f"Recent CHoCH: "
        f"{result['recent']['choch']}"
    )

    print(
        f"Recent Bullish Displacement: "
        f"{result['recent']['bullish_displacement']}"
    )

    print(
        f"Recent Bearish Displacement: "
        f"{result['recent']['bearish_displacement']}"
    )

    print("\n================================\n")


if __name__ == "__main__":
    main()
