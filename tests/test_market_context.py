import os

from app.market.market_context import (
    MarketContextEngine,
)


def main():

    engine = MarketContextEngine()

    result = engine.analyze(
        symbol="BTC",
        coin_id="bitcoin",
    )

    print(
        "\n========== MARKET CONTEXT ==========\n"
    )

    print(
        "Symbol:",
        result["symbol"],
    )

    print(
        "\n--- Providers ---"
    )

    for name, data in result[
        "providers"
    ].items():

        print(
            name,
            "=>",
            data.get("status"),
        )

    print(
        "\n--- Fundamental ---"
    )

    fundamental = result[
        "fundamental"
    ]

    for key, value in fundamental.items():

        print(
            f"{key}: {value}"
        )

    print(
        "\n--- Cross Source Comparison ---"
    )

    comparison = result[
        "comparison"
    ]

    for key, value in comparison.items():

        print(
            f"{key}: {value}"
        )

    print(
        "\n====================================\n"
    )


if __name__ == "__main__":
    main()
