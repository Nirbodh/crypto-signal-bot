import logging

from app.data.market_data import MarketDataEngine
from app.technical.technical_engine import TechnicalEngine


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)


def main():

    market_data = MarketDataEngine()

    technical = TechnicalEngine()

    df = market_data.fetch_ohlcv(
        symbol="BTC/USDT",
        timeframe="15m",
        limit=250,
        preferred_exchange="binance",
    )

    if df is None or df.empty:
        print("❌ Failed to fetch BTC/USDT")
        return

    result = technical.analyze(df)

    if result is None:
        print("❌ Technical analysis failed")
        return

    print("\n========== TECHNICAL RESULT ==========\n")

    print(
        f"Price: {result['price']}"
    )

    print(
        f"Trend: {result['trend']}"
    )

    print(
        f"RSI: {result['rsi']['value']:.2f}"
        f" | {result['rsi']['state']}"
    )

    print(
        f"MACD: {result['macd']['state']}"
    )

    print(
        f"ADX: {result['adx']['value']:.2f}"
        f" | {result['adx']['state']}"
    )

    print(
        f"Volume: "
        f"{result['volume']['ratio']:.2f}x"
        f" | {result['volume']['state']}"
    )

    print(
        f"OBV: {result['obv']['state']}"
    )

    print(
        f"VWAP: {result['vwap']['position']}"
    )

    print(
        f"Directional Bias: "
        f"{result['directional_bias']}"
    )

    print(
        f"Support: {result['support']}"
    )

    print(
        f"Resistance: {result['resistance']}"
    )

    print(
        "\n=======================================\n"
    )


if __name__ == "__main__":
    main()
