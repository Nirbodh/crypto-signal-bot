import os


class Config:
    # Runtime
    APP_NAME = "Crypto Signal Bot"
    ENVIRONMENT = os.getenv("ENVIRONMENT", "production")

    # Scanner
    SCAN_INTERVAL_MINUTES = int(
        os.getenv("SCAN_INTERVAL_MINUTES", "15")
    )

    MIN_SIGNAL_SCORE = int(
        os.getenv("MIN_SIGNAL_SCORE", "70")
    )

    STRONG_SIGNAL_SCORE = int(
        os.getenv("STRONG_SIGNAL_SCORE", "80")
    )

    A_PLUS_SIGNAL_SCORE = int(
        os.getenv("A_PLUS_SIGNAL_SCORE", "90")
    )

    # APIs
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    COINGLASS_API_KEY = os.getenv("COINGLASS_API_KEY")
    CMC_API_KEY = os.getenv("CMC_API_KEY")
    COINGECKO_API_KEY = os.getenv("COINGECKO_API_KEY")
    CRYPTOCOMPARE_API_KEY = os.getenv("CRYPTOCOMPARE_API_KEY")

    # Telegram
    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

    # MongoDB
    MONGODB_URI = os.getenv("MONGODB_URI")
    MONGODB_DATABASE = os.getenv(
        "MONGODB_DATABASE",
        "crypto_signal_bot"
    )
