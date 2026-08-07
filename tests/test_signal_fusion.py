from app.fusion.signal_fusion import (
    SignalFusionEngine,
)


def main():

    engine = SignalFusionEngine()

    technical = {
        "direction": "BULLISH",
        "score": 78,
    }

    smc = {
        "preferred_direction": "BULLISH",

        "bullish": {
            "score": 82,
        },

        "bearish": {
            "score": 35,
        },
    }

    mtf = {
        "direction": "BULLISH",
        "score": 80,
        "entry_timing": "ALIGNED",
    }

    derivatives = {
        "direction": "BULLISH",
        "score": 70,

        "funding": {
            "risk": "LOW",
        },
    }

    market = {
        "fundamental": {
            "change_24h": 4.2,
        },
    }

    result = engine.evaluate(
        technical=technical,
        smc=smc,
        mtf=mtf,
        derivatives=derivatives,
        market=market,
    )

    print(
        "\n========== FUSION RESULT ==========\n"
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
        "Grade:",
        result["grade"],
    )

    print(
        "State:",
        result["state"],
    )

    print(
        "Confluence:",
        result["confluence"],
    )

    print(
        "\nComponents:"
    )

    for name, score in result[
        "components"
    ].items():

        print(
            f"  {name}: {score}"
        )

    print(
        "\nWarnings:"
    )

    for warning in result[
        "warnings"
    ]:

        print(
            "  -",
            warning,
        )

    print(
        "\n====================================\n"
    )


if __name__ == "__main__":
    main()
