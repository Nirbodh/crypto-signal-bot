from app.execution.trade_plan import (
    TradePlanEngine,
)


def main():

    engine = TradePlanEngine()

    result = engine.build_plan(
        direction="LONG",

        entry=0.1700,

        # Example ATR
        atr=0.0040,

        # Example SMC structure
        structure_low=0.1630,

        structure_high=0.1760,
    )

    print(
        "\n========== TRADE PLAN ==========\n"
    )

    for key, value in result.items():

        print(
            f"{key}: {value}"
        )

    print(
        "\n================================\n"
    )


if __name__ == "__main__":
    main()
