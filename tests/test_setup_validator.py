from app.data.market_data import MarketDataEngine
from app.smc.smc_engine import SMCEngine
from app.smc.setup_validator import (
    SMCSetupValidator,
)


def main():

    market_data = MarketDataEngine()

    smc = SMCEngine()

    validator = SMCSetupValidator()

    df = market_data.fetch_ohlcv(
        symbol="BTC/USDT",
        timeframe="15m",
        limit=250,
        preferred_exchange="binance",
    )

    if df is None or df.empty:

        print(
            "❌ Failed to fetch BTC/USDT"
        )

        return

    smc_result = smc.analyze(df)

    if smc_result is None:

        print(
            "❌ SMC analysis failed"
        )

        return

    result = validator.evaluate(
        smc_result
    )

    print(
        "\n========== SMC SETUP ==========\n"
    )

    print(
        "Preferred:",
        result["preferred_direction"],
    )

    print(
        "\n🟢 Bullish"
    )

    print(
        "Score:",
        result["bullish"]["score"],
    )

    print(
        "Grade:",
        result["bullish"]["grade"],
    )

    print(
        "Evidence:"
    )

    for item in result[
        "bullish"
    ]["evidence"]:

        print(
            "  +",
            item,
        )

    print(
        "Warnings:"
    )

    for item in result[
        "bullish"
    ]["warnings"]:

        print(
            "  -",
            item,
        )

    print(
        "\n🔴 Bearish"
    )

    print(
        "Score:",
        result["bearish"]["score"],
    )

    print(
        "Grade:",
        result["bearish"]["grade"],
    )

    print(
        "Evidence:"
    )

    for item in result[
        "bearish"
    ]["evidence"]:

        print(
            "  +",
            item,
        )

    print(
        "Warnings:"
    )

    for item in result[
        "bearish"
    ]["warnings"]:

        print(
            "  -",
            item,
        )

    print(
        "\n================================\n"
    )


if __name__ == "__main__":
    main()
