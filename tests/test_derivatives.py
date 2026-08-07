from app.derivatives.derivatives_engine import (
    DerivativesEngine,
)


def main():

    engine = DerivativesEngine()

    # Temporary sample data.
    #
    # Later this exact structure will be
    # populated from CoinGlass.

    data = {
        "current_oi": 105_000_000,
        "previous_oi": 100_000_000,

        "price_change_pct": 3.2,

        # Example funding rate:
        # 0.008 means 0.008%
        "funding_rate": 0.008,

        "long_short_ratio": 1.12,

        "long_liquidations": 1_500_000,
        "short_liquidations": 800_000,
    }

    result = engine.analyze(
        data
    )

    print(
        "\n======= DERIVATIVES RESULT =======\n"
    )

    print(
        "Direction:",
        result["direction"],
    )

    print(
        "Score:",
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
        "\nOpen Interest:"
    )

    print(
        result["open_interest"]
    )

    print(
        "\nFunding:"
    )

    print(
        result["funding"]
    )

    print(
        "\nLong/Short:"
    )

    print(
        result["long_short"]
    )

    print(
        "\nLiquidations:"
    )

    print(
        result["liquidations"]
    )

    print(
        "\nEvidence:"
    )

    for item in result[
        "evidence"
    ]:

        print(
            " +",
            item,
        )

    print(
        "\nWarnings:"
    )

    for item in result[
        "warnings"
    ]:

        print(
            " -",
            item,
        )

    print(
        "\n===================================\n"
    )


if __name__ == "__main__":
    main()
