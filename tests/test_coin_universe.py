from app.scanner.coin_universe import (
    CoinUniverseEngine,
)


def main():

    engine = CoinUniverseEngine(
        min_quote_volume=1_000_000,
        max_coins=50,
    )

    universe = (
        engine.build_universe()
    )

    summary = (
        engine.summary(
            universe
        )
    )

    print(
        "\n========== COIN UNIVERSE ==========\n"
    )

    print(
        "Total symbols:",
        summary[
            "total_symbols"
        ],
    )

    print(
        "Exchange coverage:",
        summary[
            "exchange_coverage"
        ],
    )

    print(
        "\nTop candidates:\n"
    )

    for coin in universe[:20]:

        print(
            coin["symbol"],
            "|",
            coin["exchanges"],
            "| Volume:",
            round(
                coin[
                    "total_volume_24h"
                ],
                2,
            ),
        )

    print(
        "\n====================================\n"
    )


if __name__ == "__main__":
    main()
