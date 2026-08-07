import logging
from typing import Any, Dict, List


logger = logging.getLogger("crypto-signal-bot")


class ScannerEngine:
    """
    Main orchestration layer.

    Connects:

        Coin Universe
        Market Data
        Technical
        SMC
        Fusion
        Gemini
        Risk
        Telegram

    This class controls the workflow only.
    Individual modules keep their own logic.
    """

    def __init__(
        self,
        coin_universe,
        ohlcv_fetcher,
        technical_engine=None,
        smc_engine=None,
        fusion_engine=None,
        gemini_reviewer=None,
        trade_plan_engine=None,
        risk_engine=None,
        telegram_bot=None,
    ):

        self.coin_universe = (
            coin_universe
        )

        self.ohlcv_fetcher = (
            ohlcv_fetcher
        )

        self.technical_engine = (
            technical_engine
        )

        self.smc_engine = (
            smc_engine
        )

        self.fusion_engine = (
            fusion_engine
        )

        self.gemini_reviewer = (
            gemini_reviewer
        )

        self.trade_plan_engine = (
            trade_plan_engine
        )

        self.risk_engine = (
            risk_engine
        )

        self.telegram_bot = (
            telegram_bot
        )


    # ==========================================================
    # Scan one coin
    # ==========================================================

    def scan_symbol(
        self,
        symbol: str,
    ) -> Dict[str, Any]:

        logger.info(
            "Scanning %s",
            symbol,
        )


        # ------------------------------------------------------
        # 1. Fetch candles
        # ------------------------------------------------------

        df = (
            self.ohlcv_fetcher.fetch(
                symbol=symbol,
                timeframe="15m",
                limit=200,
            )
        )


        if df.empty:

            return {
                "status": "SKIPPED",
                "reason": (
                    "No OHLCV data"
                ),
            }


        # ------------------------------------------------------
        # 2. Technical
        # ------------------------------------------------------

        technical_result = {}


        if self.technical_engine:

            try:

                technical_result = (
                    self.technical_engine.analyze(
                        df
                    )
                )

            except Exception as exc:

                logger.warning(
                    "Technical failed %s: %s",
                    symbol,
                    exc,
                )


        # ------------------------------------------------------
        # 3. SMC
        # ------------------------------------------------------

        smc_result = {}


        if self.smc_engine:

            try:

                smc_result = (
                    self.smc_engine.analyze(
                        df
                    )
                )

            except Exception as exc:

                logger.warning(
                    "SMC failed %s: %s",
                    symbol,
                    exc,
                )


        # ------------------------------------------------------
        # 4. Fusion
        # ------------------------------------------------------

        fusion_result = {}


        if self.fusion_engine:

            fusion_result = (
                self.fusion_engine.evaluate(
                    technical=technical_result,
                    smc=smc_result,
                )
            )


        # ------------------------------------------------------
        # Minimum quality gate
        # ------------------------------------------------------

        score = fusion_result.get(
            "score",
            0,
        )


        if score < 70:

            return {

                "status": "REJECTED",

                "symbol": symbol,

                "fusion": fusion_result,

            }


        # ------------------------------------------------------
        # 5. Gemini review
        # ------------------------------------------------------

        gemini_result = {}


        if self.gemini_reviewer:

            gemini_result = (
                self.gemini_reviewer.review(
                    fusion_result
                )
            )


        # ------------------------------------------------------
        # 6. Return candidate
        # ------------------------------------------------------

        return {

            "status": "CANDIDATE",

            "symbol": symbol,

            "fusion": fusion_result,

            "gemini": gemini_result,

        }


    # ==========================================================
    # Full market scan
    # ==========================================================

    def run_scan(
        self,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:


        logger.info(
            "Building coin universe"
        )


        universe = (
            self.coin_universe
            .build_universe()
        )


        results = []


        for coin in universe[:limit]:

            symbol = coin[
                "symbol"
            ]


            try:

                result = (
                    self.scan_symbol(
                        symbol
                    )
                )


                results.append(
                    result
                )


            except Exception as exc:

                logger.exception(
                    "Scan failed %s",
                    symbol,
                )

                results.append(
                    {
                        "symbol": symbol,
                        "status": "ERROR",
                        "error": str(exc),
                    }
                )


        return results
