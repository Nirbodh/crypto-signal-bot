from app.analysis.mtf_engine import (
    MultiTimeframeEngine,
)
from app.data.market_data import (
    MarketDataEngine,
)


def main():

    market_data = MarketDataEngine()

    mtf = MultiTimeframeEngine()

    timeframe_data = {}

    configs = {
        "4h": 200,
        "1h": 200,
        "15m": 250,
        "5m": 250,
    }

    for timeframe, limit in configs.items():

        print(
            f"Fetching BTC/USDT {timeframe}..."
        )

        df = market_data.fetch_ohlcv(
            symbol="BTC/USDT",
            timeframe=timeframe,
            limit=limit,
            preferred_exchange="binance",
        )

        if df is None or df.empty:

            print(
                f"❌ Failed: {timeframe}"
            )

            continue

        timeframe_data[
            timeframe
        ] = df

    if not timeframe_data:

        print(
            "❌ No timeframe data available."
        )

        return

    result = mtf.evaluate(
        timeframe_data
    )

    print(
        "\n========== MTF RESULT ==========\n"
    )

    print(
        "Direction:",
        result["direction"],
    )

    print(
        "Overall Score:",
        result["score"],
    )

    print(
        "Bullish Score:",
        result["bullish_score"],
    )

    print(
        "Bearish Score:",
        result["bearish_score"],
    )

    print(
        "Alignment:",
        result["alignment"],
    )

    print(
        "Higher TF Agreement:",
        result[
            "higher_tf_agreement"
        ],
    )

    print(
        "Entry Timing:",
        result["entry_timing"],
    )

    print(
        "\n--- Timeframes ---"
    )

    for timeframe in (
        "4h",
        "1h",
        "15m",
        "5m",
    ):

        data = result[
            "timeframes"
        ][timeframe]

        print(
            f"{timeframe}: "
            f"{data['direction']} | "
            f"Score={data['score']} | "
            f"RSI={data['rsi']}"
        )

    print(
        "\n================================\n"
    )


if __name__ == "__main__":
    main()
