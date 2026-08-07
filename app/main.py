import logging
import os
import time


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


# Future modules

from app.fusion.signal_fusion import (
    SignalFusionEngine,
)

from app.ai.gemini_reviewer import (
    GeminiReviewer,
)

from app.execution.trade_plan import (
    TradePlanEngine,
)


# Advanced liquidity layer

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
    )

)


logger = logging.getLogger(
    "crypto-signal-bot"
)



# ==========================================================
# Create Bot
# ==========================================================

def create_bot():

    logger.info(
        "🚀 Initializing Crypto Signal Bot..."
    )


    # -----------------------------
    # Market Data
    # -----------------------------

    market_data = MarketDataEngine()


    try:

        status = (
            market_data.load_markets()
        )

        logger.info(
            "Exchange status: %s",
            status,
        )


    except Exception as exc:

        logger.warning(
            "Market loading failed: %s",
            exc,
        )



    # -----------------------------
    # Universe
    # -----------------------------

    coin_universe = CoinUniverseEngine(

        max_coins=100

    )


    # -----------------------------
    # Liquidity Ranking
    # -----------------------------

    liquidity = LiquidityRanker(
        market_data
    )


    try:

        ranked = (
            liquidity.build_ranked_universe(

                minimum_volume=1_000_000,

                maximum_coins=250

            )
        )


        if not ranked.empty:

            logger.info(
                "Top liquid coins loaded: %s",
                len(ranked),
            )


    except Exception as exc:

        logger.warning(
            "Liquidity ranking failed: %s",
            exc,
        )



    # -----------------------------
    # Analysis Engines
    # -----------------------------

    ohlcv = OHLCVFetcher()


    fusion = SignalFusionEngine()


    gemini = GeminiReviewer()


    trade_plan = TradePlanEngine()


    risk = RiskEngine()


    telegram = TelegramBot()



    # -----------------------------
    # Main Engine
    # -----------------------------

    scanner = ScannerEngine(

        coin_universe=coin_universe,

        ohlcv_fetcher=ohlcv,

        fusion_engine=fusion,

        gemini_reviewer=gemini,

        trade_plan_engine=trade_plan,

        risk_engine=risk,

        telegram_bot=telegram,

    )


    return scanner, telegram, market_data




# ==========================================================
# Worker
# ==========================================================

def main():


    scanner, telegram, market_data = (
        create_bot()
    )


    interval = int(

        os.getenv(

            "SCAN_INTERVAL",

            3600

        )

    )



    logger.info(
        "✅ Bot is running 24/7"
    )


    telegram.send_status(
        "🟢 Crypto Signal Bot Started"
    )



    while True:


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

                x

                for x in results

                if x.get(
                    "status"
                )
                == "CANDIDATE"

            ]



            logger.info(
                "🎯 Found candidates: %s",
                len(candidates),
            )



            for signal in candidates:


                logger.info(
                    "⭐ %s",
                    signal.get(
                        "symbol"
                    ),
                )


                # Telegram final connection
                # will be activated after
                # signal schema locking.



            logger.info(
                "✅ Scan finished"
            )



        except Exception as exc:


            logger.exception(
                "Scanner error: %s",
                exc,
            )



        logger.info(
            "Sleeping %s seconds",
            interval,
        )


        time.sleep(
            interval
        )



if __name__ == "__main__":

    main()
