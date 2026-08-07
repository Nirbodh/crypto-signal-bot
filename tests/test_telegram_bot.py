from app.telegram.telegram_bot import (
    TelegramBot,
)


def main():

    bot = TelegramBot()

    signal = {

        "symbol": "STG/USDT",

        "direction": "LONG",

        "score": 84,

        "grade": "A",

        "confluence": 82,

        "components": {
            "technical": 82,
            "smc": 88,
            "mtf": 80,
            "derivatives": 74,
            "market": 69,
        },

        "trade_plan": {
            "entry": 0.1700,
            "stop_loss": 0.1630,
            "tp1": 0.1770,
            "tp2": 0.1840,
            "tp3": 0.1910,
        },

        "risk": {
            "position": {
                "risk_percent": 1.0,
                "position_notional": 242.86,
            },

            "leverage": {
                "leverage": 5,
            },
        },

        "gemini": {
            "verdict": "CONFIRM",
            "confidence": 84,
            "reason": (
                "Strong SMC and MTF confluence"
            ),
            "risk_flags": [],
        },

        "warnings": [],
    }

    print(
        "\n========== TELEGRAM PREVIEW ==========\n"
    )

    message = bot.format_signal(
        signal
    )

    print(message)

    print(
        "\n=======================================\n"
    )

    # Do NOT send automatically during
    # local development.
    #
    # Uncomment only when Telegram credentials
    # are configured and you want to test delivery.

    # result = bot.send_signal(signal)
    # print(result)


if __name__ == "__main__":
    main()
