import os
import sys
import time
import logging
import threading
from typing import Optional

# ==========================================================
# Python Path
# ==========================================================

BASE_DIR = os.path.dirname(
    os.path.dirname(
        os.path.abspath(__file__)
    )
)

if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)


# ==========================================================
# Third-party
# ==========================================================

from flask import Flask, jsonify


# ==========================================================
# Project Imports
# ==========================================================

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

from app.technical.technical_engine import (
    TechnicalEngine,
)

from app.smc.smc_engine import (
    SMCEngine,
)

from app.analysis.mtf_engine import (
    MultiTimeframeEngine,
)

from app.derivatives.derivatives_engine import (
    DerivativesEngine,
)

from app.market.market_context import (
    MarketContextEngine,
)

from app.smc.setup_validator import (
    SMCSetupValidator,
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
# Global State
# ==========================================================

scanner: Optional[ScannerEngine] = None
telegram: Optional[TelegramBot] = None
market_data: Optional[MarketDataEngine] = None

last_scan_time = None
last_scan_status = "NOT_STARTED"

bot_started = False

bot_initializing = False

scan_running = False

startup_lock = threading.Lock()
scan_lock = threading.Lock()


# ==========================================================
# Health Endpoint
# ==========================================================

@app.route(
    "/health",
    methods=["GET"],
)
def health():

    return jsonify(
        {
            "status": "ok",
            "service": "crypto-signal-bot",
            "bot_started": bot_started,
            "bot_initializing": bot_initializing,
            "scan_running": scan_running,
            "last_scan": last_scan_time,
            "last_scan_status": last_scan_status,
        }
    ), 200


# ==========================================================
# Root Endpoint
# ==========================================================

@app.route(
    "/",
    methods=["GET"],
)
def root():

    return jsonify(
        {
            "service": "Crypto Signal Bot",
            "status": "running",
            "bot_started": bot_started,
            "last_scan_status": last_scan_status,
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

    market_data_engine = MarketDataEngine()

    try:

        market_status = (
            market_data_engine.load_markets()
        )

        logger.info(
            "📊 Exchange status: %s",
            market_status,
        )

    except Exception as exc:

        logger.warning(
            "⚠️ Market loading failed: %s",
            exc,
        )

    # ------------------------------------------------------
    # Coin Universe
    # ------------------------------------------------------

    coin_engine = CoinUniverseEngine(
        max_coins=100
    )

    # ------------------------------------------------------
    # Liquidity Ranking
    # ------------------------------------------------------

    liquidity_ranker = LiquidityRanker(
        market_data_engine
    )

    try:

        ranked = (
            liquidity_ranker
            .build_ranked_universe(
                minimum_volume=1_000_000,
                maximum_coins=250,
            )
        )

        if ranked is not None and not ranked.empty:

            logger.info(
                "🏆 Liquid universe: %s coins",
                len(ranked),
            )

        else:

            logger.warning(
                "⚠️ Liquidity universe is empty"
            )

    except Exception as exc:

        logger.warning(
            "⚠️ Liquidity ranking failed: %s",
            exc,
        )

    # ------------------------------------------------------
    # OHLCV
    # ------------------------------------------------------

    ohlcv_engine = OHLCVFetcher()

    # ------------------------------------------------------
    # Analysis Engines
    # ------------------------------------------------------

    technical_engine = TechnicalEngine()
    smc_engine = SMCEngine()
    mtf_engine = MultiTimeframeEngine()
    derivatives_engine = DerivativesEngine()
    market_context_engine = MarketContextEngine()
    setup_validator = SMCSetupValidator()

    # ------------------------------------------------------
    # Signal Fusion
    # ------------------------------------------------------

    fusion_engine = SignalFusionEngine()

    # ------------------------------------------------------
    # Gemini
    # ------------------------------------------------------

    gemini_engine = GeminiReviewer()

    # ------------------------------------------------------
    # Trade Plan
    # ------------------------------------------------------

    trade_plan_engine = TradePlanEngine()

    # ------------------------------------------------------
    # Risk
    # ------------------------------------------------------

    risk_engine = RiskEngine()

    # ------------------------------------------------------
    # Telegram
    # ------------------------------------------------------

    telegram_bot = TelegramBot()

    # ------------------------------------------------------
    # Scanner
    # ------------------------------------------------------

    scanner_engine = ScannerEngine(

        coin_universe=coin_engine,

        ohlcv_fetcher=ohlcv_engine,

        technical_engine=technical_engine,

        smc_engine=smc_engine,

        mtf_engine=mtf_engine,

        derivatives_engine=derivatives_engine,

        market_context_engine=market_context_engine,

        setup_validator=setup_validator,

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
    global scan_running

    # ------------------------------------------------------
    # Prevent duplicate scans
    # ------------------------------------------------------

    if not scan_lock.acquire(
        blocking=False
    ):

        logger.warning(
            "⚠️ Scan already running. Skipping."
        )

        return

    scan_running = True

    try:

        if scanner is None:

            logger.error(
                "❌ Scanner is not initialized."
            )

            last_scan_status = (
                "SCANNER_NOT_INITIALIZED"
            )

            return

        logger.info(
            "🔍 Starting market scan..."
        )

        last_scan_status = (
            "RUNNING"
        )

        # --------------------------------------------------
        # Run Scanner
        # --------------------------------------------------

        results = scanner.run_scan(
            limit=20
        )

        if results is None:

            results = []

        candidates = [
            item
            for item in results
            if isinstance(item, dict)
            and item.get("status")
            == "CANDIDATE"
        ]

        logger.info(
            "🎯 Candidates found: %s",
            len(candidates),
        )

        # --------------------------------------------------
        # Candidate Logging
        # --------------------------------------------------

        for candidate in candidates:

            logger.info(
                "⭐ Candidate: %s | Score: %s | Direction: %s",
                candidate.get("symbol"),
                candidate.get("score"),
                candidate.get("direction"),
            )

        # --------------------------------------------------
        # Final Status
        # --------------------------------------------------

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
            "✅ Scan completed successfully"
        )

    except Exception as exc:

        last_scan_status = (
            "ERROR"
        )

        last_scan_time = (
            time.strftime(
                "%Y-%m-%d %H:%M:%S UTC",
                time.gmtime(),
            )
        )

        logger.exception(
            "❌ Scan failed: %s",
            exc,
        )

    finally:

        scan_running = False

        scan_lock.release()


# ==========================================================
# Scheduler
# ==========================================================

def scheduler_loop():

    try:

        scan_interval = int(
            os.getenv(
                "SCAN_INTERVAL",
                "3600",
            )
        )

    except (
        TypeError,
        ValueError,
    ):

        scan_interval = 3600

    if scan_interval < 60:

        logger.warning(
            "⚠️ SCAN_INTERVAL too low. "
            "Using minimum 60 seconds."
        )

        scan_interval = 60

    logger.info(
        "⏰ Scanner interval: %s seconds",
        scan_interval,
    )

    # ------------------------------------------------------
    # Initial Scan
    # ------------------------------------------------------

    perform_scan()

    # ------------------------------------------------------
    # Continuous Scheduler
    # ------------------------------------------------------

    while True:

        try:

            time.sleep(
                scan_interval
            )

            perform_scan()

        except Exception as exc:

            logger.exception(
                "❌ Scheduler error: %s",
                exc,
            )

            time.sleep(30)


# ==========================================================
# Initialize Bot
# ==========================================================

def initialize_bot():

    global scanner
    global telegram
    global market_data
    global bot_started
    global bot_initializing

    # ------------------------------------------------------
    # Already Started
    # ------------------------------------------------------

    if bot_started:

        logger.info(
            "ℹ️ Bot already initialized."
        )

        return

    # ------------------------------------------------------
    # Prevent Duplicate Initialization
    # ------------------------------------------------------

    if not startup_lock.acquire(
        blocking=False
    ):

        logger.warning(
            "⚠️ Bot initialization already in progress."
        )

        return

    bot_initializing = True

    try:

        logger.info(
            "⚙️ Creating bot components..."
        )

        (
            scanner_instance,
            telegram_instance,
            market_data_instance,
        ) = create_bot()

        scanner = scanner_instance
        telegram = telegram_instance
        market_data = market_data_instance

        bot_started = True

        logger.info(
            "🟢 Bot initialized successfully"
        )

        # --------------------------------------------------
        # Telegram Startup Message
        # --------------------------------------------------

        try:

            telegram.send_status(
                "🟢 Crypto Signal Bot started on Render"
            )

            logger.info(
                "📨 Telegram startup message sent"
            )

        except Exception as exc:

            logger.warning(
                "⚠️ Telegram startup message failed: %s",
                exc,
            )

        # --------------------------------------------------
        # Scheduler Thread
        # --------------------------------------------------

        thread = threading.Thread(
            target=scheduler_loop,
            name="crypto-scanner",
            daemon=True,
        )

        thread.start()

        logger.info(
            "⏰ Background scanner started"
        )

    except Exception as exc:

        bot_started = False

        logger.exception(
            "❌ Bot initialization failed: %s",
            exc,
        )

    finally:

        bot_initializing = False

        startup_lock.release()


# ==========================================================
# Manual Scan Endpoint
# ==========================================================

@app.route(
    "/scan",
    methods=["GET"],
)
def manual_scan():

    if not bot_started:

        return jsonify(
            {
                "status": "error",
                "message": "Bot is not initialized",
            }
        ), 503

    if scan_running:

        return jsonify(
            {
                "status": "busy",
                "message": "A scan is already running",
            }
        ), 409

    thread = threading.Thread(
        target=perform_scan,
        name="manual-scan",
        daemon=True,
    )

    thread.start()

    return jsonify(
        {
            "status": "accepted",
            "message": "Market scan started",
        }
    ), 202


# ==========================================================
# Gunicorn / Render Startup
# ==========================================================

if os.getenv("RENDER"):

    logger.info(
        "☁️ Render environment detected."
    )

    initialize_bot()


# ==========================================================
# Local Development
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
        "🌐 Starting local web server on port %s",
        port,
    )

    app.run(
        host="0.0.0.0",
        port=port,
        threaded=True,
    )
