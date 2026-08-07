from app.risk.risk_engine import (
    RiskEngine,
)


def main():

    engine = RiskEngine()

    result = engine.build_plan(

        account_balance=1000,

        entry_price=0.1700,

        stop_loss=0.1630,

        signal_score=82,

        requested_risk_percent=1.0,

        requested_leverage=5,
    )

    print(
        "\n========== RISK PLAN ==========\n"
    )

    print(
        "Status:",
        result["status"],
    )

    print(
        "\nPosition:"
    )

    for key, value in result[
        "position"
    ].items():

        print(
            f"  {key}: {value}"
        )

    print(
        "\nLeverage:"
    )

    for key, value in result[
        "leverage"
    ].items():

        print(
            f"  {key}: {value}"
        )

    print(
        "\nWarnings:"
    )

    for warning in result[
        "warnings"
    ]:

        print(
            " -",
            warning,
        )

    print(
        "\n================================\n"
    )


if __name__ == "__main__":
    main()
