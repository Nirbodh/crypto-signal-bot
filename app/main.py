import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import logging
import os
import threading
import time

from flask import Flask, jsonify

from app.scanner.coin_universe import (
    CoinUniverseEngine,
)

from app.market_data.ohlcv_fetcher import (
    OHLCVFetcher,
)

from app.core.scanner_engine import (
    ScannerEngine,
)

from app.risk.risk_engine import (
    RiskEngine,
)

from app.telegram.telegram_bot import (
    TelegramBot,
)

from app.fusion.signal_fusion import (
    SignalFusionEngine,
)

from app.ai.gemini_reviewer import (
    GeminiReviewer,
)

from app.execution.trade_plan import (
    TradePlanEngine,
)

from app.data.market_data import (
    MarketDataEngine,
)

from app.universe.liquidity_ranker import (
    LiquidityRanker,
)


# ==========================================================
# Logging
# ==========================================================

logging.basicConfig(
    level=logging.INFO,
    format=(
        "%(asctime)s | "
        "%(levelname)s | "
        "%(message)s"
    ),
)

logger = logging.getLogger(
    "crypto-signal-bot"
)


# ==========================================================
# Flask
# ==========================================================

app = Flask(__name__)


# ==========================================================
# Global state
# ==========================================================

scanner = None
telegram = None
market_data = None

last_scan_time = None
last_scan_status = "NOT_STARTED"

bot_started = False


# ==========================================================
# Health Endpoint
# ==========================================================

@app.route("/health", methods=["GET"])
def health():

    return jsonify(
        {
            "status": "ok",
            "service": "crypto-signal-bot",
            "bot_started": bot_started,
            "last_scan": last_scan_time,
            "last_scan_status": last_scan_status,
        }
    ), 200


# ==========================================================
# Root Endpoint
# ==========================================================

@app.route("/", methods=["GET"])
def root():

    return jsonify(
        {
            "service": "Crypto Signal Bot",
            "status": "running",
            "health": "/health",
        }
    ), 200


# ==========================================================
# Build Bot
# ==========================================================

def create_bot():

    logger.info(
        "🚀 Initializing Crypto Signal Bot..."
    )

    # ------------------------------------------------------
    # Market Data
    # ------------------------------------------------------

    market_data_engine = (
        MarketDataEngine()
    )

    try:

        market_status = (
            market_data_engine
            .load_markets()
        )

        logger.info(
            "Exchange status: %s",
            market_status,
        )

    except Exception as exc:

        logger.warning(
            "Market loading failed: %s",
            exc,
        )

    # ------------------------------------------------------
    # Coin Universe
    # ------------------------------------------------------

    coin_engine = (
        CoinUniverseEngine(
            max_coins=100
        )
    )

    # ------------------------------------------------------
    # Liquidity
    # ------------------------------------------------------

    liquidity_ranker = (
        LiquidityRanker(
            market_data_engine
        )
    )

    try:

        ranked = (
            liquidity_ranker
            .build_ranked_universe(
                minimum_volume=1_000_000,
                maximum_coins=250,
            )
        )

        if not ranked.empty:

            logger.info(
                "🏆 Liquid universe: %s coins",
                len(ranked),
            )

    except Exception as exc:

        logger.warning(
            "Liquidity ranking failed: %s",
            exc,
        )

    # ------------------------------------------------------
    # Engines
    # ------------------------------------------------------

    ohlcv_engine = (
        OHLCVFetcher()
    )

    fusion_engine = (
        SignalFusionEngine()
    )

    gemini_engine = (
        GeminiReviewer()
    )

    trade_plan_engine = (
        TradePlanEngine()
    )

    risk_engine = (
        RiskEngine()
    )

    telegram_bot = (
        TelegramBot()
    )

    # ------------------------------------------------------
    # Scanner
    # ------------------------------------------------------

    scanner_engine = ScannerEngine(

        coin_universe=coin_engine,

        ohlcv_fetcher=ohlcv_engine,

        fusion_engine=fusion_engine,

        gemini_reviewer=gemini_engine,

        trade_plan_engine=trade_plan_engine,

        risk_engine=risk_engine,

        telegram_bot=telegram_bot,
    )

    return (
        scanner_engine,
        telegram_bot,
        market_data_engine,
    )


# ==========================================================
# Scan
# ==========================================================

def perform_scan():

    global last_scan_time
    global last_scan_status

    try:

        logger.info(
            "🔍 Starting market scan..."
        )

        results = (
            scanner.run_scan(
                limit=20
            )
        )

        candidates = [
            item
            for item in results
            if item.get("status")
            == "CANDIDATE"
        ]

        logger.info(
            "🎯 Candidates found: %s",
            len(candidates),
        )

        # --------------------------------------------------
        # Telegram
        # --------------------------------------------------

        for candidate in candidates:

            logger.info(
                "⭐ Candidate: %s",
                candidate.get(
                    "symbol"
                ),
            )

            # Final Telegram signal formatting
            # will be connected after the
            # signal schema is locked.

        last_scan_status = (
            "SUCCESS"
        )

        last_scan_time = (
            time.strftime(
                "%Y-%m-%d %H:%M:%S UTC",
                time.gmtime(),
            )
        )

        logger.info(
            "✅ Scan completed"
        )

    except Exception as exc:

        last_scan_status = (
            "ERROR"
        )

        logger.exception(
            "❌ Scan failed: %s",
            exc,
        )


# ==========================================================
# Scheduler
# ==========================================================

def scheduler_loop():

    scan_interval = int(
        os.getenv(
            "SCAN_INTERVAL",
            "3600",
        )
    )

    logger.info(
        "⏰ Scanner interval: %s seconds",
        scan_interval,
    )

    # Initial scan

    perform_scan()

    while True:

        time.sleep(
            scan_interval
        )

        perform_scan()


# ==========================================================
# Startup
# ==========================================================

def initialize_bot():

    global scanner
    global telegram
    global market_data
    global bot_started

    logger.info(
        "⚙️ Creating bot components..."
    )

    (
        scanner,
        telegram,
        market_data,
    ) = create_bot()

    bot_started = True

    logger.info(
        "🟢 Bot initialized successfully"
    )

    # ------------------------------------------------------
    # Telegram startup message
    # ------------------------------------------------------

    try:

        telegram.send_status(
            "🟢 Crypto Signal Bot started on Render"
        )

    except Exception as exc:

        logger.warning(
            "Telegram startup message failed: %s",
            exc,
        )

    # ------------------------------------------------------
    # Scheduler thread
    # ------------------------------------------------------

    thread = threading.Thread(
        target=scheduler_loop,
        daemon=True,
    )

    thread.start()

    logger.info(
        "⏰ Scheduler started"
    )


# ==========================================================
# Main
# ==========================================================

if __name__ == "__main__":

    initialize_bot()

    port = int(
        os.getenv(
            "PORT",
            "10000",
        )
    )

    logger.info(
        "🌐 Starting web server on port %s",
        port,
    )

    app.run(
        host="0.0.0.0",
        port=port,
        threaded=True,
    )
