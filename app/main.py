import time
import logging

from app.config import Config


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

logger = logging.getLogger("crypto-signal-bot")


def run():
    logger.info("🚀 Crypto Signal Bot started")
    logger.info(
        "Scan interval: %s minutes",
        Config.SCAN_INTERVAL_MINUTES
    )
    logger.info(
        "Minimum signal score: %s",
        Config.MIN_SIGNAL_SCORE
    )

    while True:
        try:
            logger.info("🔎 Scanner cycle started")

            # Scanner modules will be added here.
            # For now this is only the foundation.

            logger.info("✅ Scanner cycle completed")

        except Exception as exc:
            logger.exception(
                "❌ Scanner cycle failed: %s",
                exc
            )

        time.sleep(
            Config.SCAN_INTERVAL_MINUTES * 60
        )


if __name__ == "__main__":
    run()
