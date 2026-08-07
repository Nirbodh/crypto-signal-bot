from app.ai.gemini_reviewer import (
    GeminiReviewer,
)


def main():

    reviewer = GeminiReviewer()

    analysis = {
        "symbol": "BTCUSDT",

        "direction": "BULLISH",

        "score": 82,

        "grade": "A",

        "state": "TRADE_CANDIDATE",

        "confluence": 80,

        "components": {
            "technical": 78,
            "smc": 86,
            "mtf": 82,
            "derivatives": 71,
            "market": 68,
            "ai": 50,
        },

        "warnings": [
            "5m entry timing is neutral",
        ],
    }

    result = reviewer.review(
        analysis
    )

    print(
        "\n========== GEMINI REVIEW ==========\n"
    )

    print(
        "Status:",
        result.get("status"),
    )

    print(
        "Verdict:",
        result.get("verdict"),
    )

    print(
        "Confidence:",
        result.get("confidence"),
    )

    print(
        "Reason:",
        result.get("reason"),
    )

    print(
        "\nRisk flags:"
    )

    for item in result.get(
        "risk_flags",
        [],
    ):

        print(
            " -",
            item,
        )

    print(
        "\nBullish factors:"
    )

    for item in result.get(
        "bullish_factors",
        [],
    ):

        print(
            " +",
            item,
        )

    print(
        "\nBearish factors:"
    )

    for item in result.get(
        "bearish_factors",
        [],
    ):

        print(
            " -",
            item,
        )

    print(
        "\n====================================\n"
    )


if __name__ == "__main__":
    main()
