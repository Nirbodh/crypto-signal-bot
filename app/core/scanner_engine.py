import logging
from typing import Any, Dict, List


logger = logging.getLogger("crypto-signal-bot")


class ScannerEngine:
    """
    Main orchestration layer for the Crypto Signal Bot.

    Workflow:

        Coin Universe
              ↓
        OHLCV Fetcher
              ↓
        Technical Analysis
              ↓
        SMC Analysis
              ↓
        Signal Fusion
              ↓
        Quality Gate
              ↓
        Gemini Review
              ↓
        Trade Plan
              ↓
        Risk Engine
              ↓
        Candidate / Rejection

    This class orchestrates the workflow.
    Individual modules keep their own calculation logic.
    """

    def __init__(
        self,
        coin_universe,
        ohlcv_fetcher,
        technical_engine=None,
        smc_engine=None,
        mtf_engine=None,
        derivatives_engine=None,
        market_context_engine=None,
        setup_validator=None,
        fusion_engine=None,
        gemini_reviewer=None,
        trade_plan_engine=None,
        risk_engine=None,
        telegram_bot=None,
    ):

        self.coin_universe = coin_universe
        self.ohlcv_fetcher = ohlcv_fetcher

        self.technical_engine = technical_engine
        self.smc_engine = smc_engine
        self.mtf_engine = mtf_engine
        self.derivatives_engine = derivatives_engine
        self.market_context_engine = market_context_engine
        self.setup_validator = setup_validator
        self.fusion_engine = fusion_engine
        self.gemini_reviewer = gemini_reviewer
        self.trade_plan_engine = trade_plan_engine
        self.risk_engine = risk_engine
        self.telegram_bot = telegram_bot

        logger.info(
            "ScannerEngine initialized | "
            "technical=%s | "
            "smc=%s | "
            "fusion=%s | "
            "gemini=%s | "
            "risk=%s",
            bool(self.technical_engine),
            bool(self.smc_engine),
            bool(self.fusion_engine),
            bool(self.gemini_reviewer),
            bool(self.risk_engine),
        )

    # ==========================================================
    # Scan One Symbol
    # ==========================================================

    def scan_symbol(
        self,
        symbol: str,
    ) -> Dict[str, Any]:

        logger.info(
            "🔍 Scanning %s",
            symbol,
        )

        # ------------------------------------------------------
        # 1. Fetch OHLCV
        # ------------------------------------------------------

        try:

            df = self.ohlcv_fetcher.fetch(
                symbol=symbol,
                timeframe="15m",
                limit=200,
            )

        except Exception as exc:

            logger.warning(
                "OHLCV fetch failed %s: %s",
                symbol,
                exc,
            )

            return {
                "status": "SKIPPED",
                "symbol": symbol,
                "reason": "OHLCV_FETCH_FAILED",
                "error": str(exc),
            }

        # ------------------------------------------------------
        # Validate OHLCV
        # ------------------------------------------------------

        if df is None:

            logger.warning(
                "OHLCV returned None | %s",
                symbol,
            )

            return {
                "status": "SKIPPED",
                "symbol": symbol,
                "reason": "NO_OHLCV_DATA",
            }

        if getattr(df, "empty", True):

            logger.warning(
                "OHLCV empty | %s",
                symbol,
            )

            return {
                "status": "SKIPPED",
                "symbol": symbol,
                "reason": "EMPTY_OHLCV",
            }

        if len(df) < 50:

            logger.warning(
                "Insufficient candles | %s | candles=%s",
                symbol,
                len(df),
            )

            return {
                "status": "SKIPPED",
                "symbol": symbol,
                "reason": "INSUFFICIENT_CANDLES",
                "candles": len(df),
            }

        logger.info(
            "OHLCV ready | %s | candles=%s",
            symbol,
            len(df),
        )

        # ------------------------------------------------------
        # 2. Technical Analysis
        # ------------------------------------------------------

        technical_result: Dict[str, Any] = {}

        if self.technical_engine:

            try:

                technical_result = (
                    self.technical_engine.analyze(df)
                    or {}
                )

                logger.info(
                    "Technical analysis complete | %s",
                    symbol,
                )

            except Exception as exc:

                logger.exception(
                    "Technical analysis failed | %s: %s",
                    symbol,
                    exc,
                )

        else:

            logger.warning(
                "⚠️ Technical engine not configured | %s",
                symbol,
            )

        # ------------------------------------------------------
        # 3. SMC Analysis
        # ------------------------------------------------------

        smc_result: Dict[str, Any] = {}

        if self.smc_engine:

            try:

                smc_result = (
                    self.smc_engine.analyze(df)
                    or {}
                )

                logger.info(
                    "SMC analysis complete | %s",
                    symbol,
                )

            except Exception as exc:

                logger.exception(
                    "SMC analysis failed | %s: %s",
                    symbol,
                    exc,
                )

        else:

            logger.warning(
                "⚠️ SMC engine not configured | %s",
                symbol,
            )

        # ------------------------------------------------------
        # 4. MTF Analysis (if available)
        # ------------------------------------------------------

        mtf_result: Dict[str, Any] = {}

        if self.mtf_engine:

            try:

                mtf_result = (
                    self.mtf_engine.evaluate({})
                    or {}
                )

                logger.info(
                    "MTF analysis complete | %s",
                    symbol,
                )

            except Exception as exc:

                logger.exception(
                    "MTF analysis failed | %s: %s",
                    symbol,
                    exc,
                )

        # ------------------------------------------------------
        # 5. Derivatives Analysis (if available)
        # ------------------------------------------------------

        derivatives_result: Dict[str, Any] = {}

        if self.derivatives_engine:

            try:

                derivatives_result = (
                    self.derivatives_engine.analyze({})
                    or {}
                )

                logger.info(
                    "Derivatives analysis complete | %s",
                    symbol,
                )

            except Exception as exc:

                logger.exception(
                    "Derivatives analysis failed | %s: %s",
                    symbol,
                    exc,
                )

        # ------------------------------------------------------
        # 6. Market Context (if available)
        # ------------------------------------------------------

        market_result: Dict[str, Any] = {}

        if self.market_context_engine:

            try:

                market_result = (
                    self.market_context_engine.analyze(symbol)
                    or {}
                )

                logger.info(
                    "Market context complete | %s",
                    symbol,
                )

            except Exception as exc:

                logger.exception(
                    "Market context failed | %s: %s",
                    symbol,
                    exc,
                )

        # ------------------------------------------------------
        # Safety Gate
        # ------------------------------------------------------

        if (
            not technical_result
            and not smc_result
        ):

            logger.warning(
                "No technical/SMC data available | %s",
                symbol,
            )

            return {
                "status": "SKIPPED",
                "symbol": symbol,
                "reason": "NO_ANALYSIS_DATA",
            }

        # ------------------------------------------------------
        # 7. Signal Fusion
        # ------------------------------------------------------

        fusion_result: Dict[str, Any] = {}

        if self.fusion_engine:

            try:

                fusion_result = (
                    self.fusion_engine.evaluate(
                        technical=technical_result,
                        smc=smc_result,
                        mtf=mtf_result,
                        derivatives=derivatives_result,
                        market=market_result,
                    )
                    or {}
                )

            except Exception as exc:

                logger.exception(
                    "Fusion failed | %s: %s",
                    symbol,
                    exc,
                )

                return {
                    "status": "ERROR",
                    "symbol": symbol,
                    "reason": "FUSION_FAILED",
                    "error": str(exc),
                    "technical": technical_result,
                    "smc": smc_result,
                }

        else:

            logger.warning(
                "⚠️ Fusion engine not configured | %s",
                symbol,
            )

            return {
                "status": "SKIPPED",
                "symbol": symbol,
                "reason": "NO_FUSION_ENGINE",
                "technical": technical_result,
                "smc": smc_result,
            }

        # ------------------------------------------------------
        # Fusion Summary
        # ------------------------------------------------------

        score = float(
            fusion_result.get(
                "score",
                0,
            ) or 0
        )

        direction = fusion_result.get(
            "direction",
            "NEUTRAL",
        )

        grade = fusion_result.get(
            "grade",
            "D",
        )

        state = fusion_result.get(
            "state",
            "UNKNOWN",
        )

        logger.info(
            "Fusion result | %s | "
            "direction=%s | "
            "score=%.2f | "
            "grade=%s | "
            "state=%s",
            symbol,
            direction,
            score,
            grade,
            state,
        )

        # ------------------------------------------------------
        # 8. Quality Gate
        # ------------------------------------------------------
        #
        # IMPORTANT:
        # We do NOT call Gemini for weak setups.
        #
        # This protects API usage.
        #

        minimum_score = 70.0

        if score < minimum_score:

            logger.info(
                "❌ Rejected by quality gate | "
                "%s | score=%.2f < %.2f",
                symbol,
                score,
                minimum_score,
            )

            return {
                "status": "REJECTED",
                "symbol": symbol,
                "score": score,
                "direction": direction,
                "grade": grade,
                "state": state,
                "technical": technical_result,
                "smc": smc_result,
                "fusion": fusion_result,
                "reason": "QUALITY_GATE",
            }

        # ------------------------------------------------------
        # Direction Gate
        # ------------------------------------------------------

        if direction == "NEUTRAL":

            logger.info(
                "❌ Neutral setup rejected | %s",
                symbol,
            )

            return {
                "status": "REJECTED",
                "symbol": symbol,
                "score": score,
                "direction": direction,
                "grade": grade,
                "state": state,
                "technical": technical_result,
                "smc": smc_result,
                "fusion": fusion_result,
                "reason": "NEUTRAL_DIRECTION",
            }

        # ------------------------------------------------------
        # 9. Gemini Review
        # ------------------------------------------------------

        gemini_result: Dict[str, Any] = {}

        if self.gemini_reviewer:

            try:

                review_payload = {
                    "symbol": symbol,
                    "technical": technical_result,
                    "smc": smc_result,
                    "fusion": fusion_result,
                    "mtf": mtf_result,
                    "derivatives": derivatives_result,
                    "market": market_result,
                }

                gemini_result = (
                    self.gemini_reviewer.review(
                        review_payload
                    )
                    or {}
                )

                logger.info(
                    "🤖 Gemini review complete | %s",
                    symbol,
                )

            except Exception as exc:

                logger.warning(
                    "Gemini review failed | %s: %s",
                    symbol,
                    exc,
                )

                gemini_result = {
                    "status": "ERROR",
                    "error": str(exc),
                }

        # ------------------------------------------------------
        # 10. Gemini Decision Gate
        # ------------------------------------------------------

        # Check both 'decision' and 'verdict' fields
        gemini_decision = str(
            gemini_result.get(
                "decision",
                gemini_result.get(
                    "verdict",
                    "UNKNOWN",
                ),
            )
        ).upper()

        if gemini_decision in {
            "REJECT",
            "REJECTED",
            "NO_TRADE",
        }:

            logger.info(
                "❌ Gemini rejected setup | %s",
                symbol,
            )

            return {
                "status": "REJECTED",
                "symbol": symbol,
                "score": score,
                "direction": direction,
                "grade": grade,
                "state": state,
                "technical": technical_result,
                "smc": smc_result,
                "fusion": fusion_result,
                "gemini": gemini_result,
                "reason": "GEMINI_REJECTION",
            }

        # ------------------------------------------------------
        # 11. Trade Plan
        # ------------------------------------------------------

        trade_plan: Dict[str, Any] = {}

        if self.trade_plan_engine:

            try:

                trade_plan = (
                    self.trade_plan_engine.build(
                        symbol=symbol,
                        dataframe=df,
                        fusion_result=fusion_result,
                        gemini_result=gemini_result,
                    )
                    or {}
                )

                logger.info(
                    "📐 Trade plan generated | %s",
                    symbol,
                )

            except Exception as exc:

                logger.warning(
                    "Trade plan failed | %s: %s",
                    symbol,
                    exc,
                )

                trade_plan = {
                    "status": "ERROR",
                    "error": str(exc),
                }

        # ------------------------------------------------------
        # 12. Risk Engine
        # ------------------------------------------------------

        risk_result: Dict[str, Any] = {}

        if self.risk_engine:

            try:

                risk_result = (
                    self.risk_engine.evaluate(
                        symbol=symbol,
                        fusion_result=fusion_result,
                        gemini_result=gemini_result,
                        trade_plan=trade_plan,
                    )
                    or {}
                )

                logger.info(
                    "🛡️ Risk evaluation complete | %s",
                    symbol,
                )

            except Exception as exc:

                logger.warning(
                    "Risk evaluation failed | %s: %s",
                    symbol,
                    exc,
                )

                risk_result = {
                    "status": "ERROR",
                    "error": str(exc),
                }

        # ------------------------------------------------------
        # 13. Final Risk Gate
        # ------------------------------------------------------

        risk_decision = str(
            risk_result.get(
                "decision",
                risk_result.get(
                    "status",
                    "UNKNOWN",
                ),
            )
        ).upper()

        if risk_decision in {
            "REJECT",
            "REJECTED",
            "NO_TRADE",
            "BLOCK",
            "BLOCKED",
            "INVALID",
        }:

            logger.info(
                "🛑 Risk engine blocked setup | %s",
                symbol,
            )

            return {
                "status": "REJECTED",
                "symbol": symbol,
                "score": score,
                "direction": direction,
                "grade": grade,
                "state": state,
                "technical": technical_result,
                "smc": smc_result,
                "fusion": fusion_result,
                "gemini": gemini_result,
                "trade_plan": trade_plan,
                "risk": risk_result,
                "reason": "RISK_ENGINE",
            }

        # ------------------------------------------------------
        # 14. FINAL CANDIDATE
        # ------------------------------------------------------

        logger.info(
            "🎯 CANDIDATE | %s | score=%.2f | direction=%s",
            symbol,
            score,
            direction,
        )

        return {
            "status": "CANDIDATE",
            "symbol": symbol,
            "score": score,
            "direction": direction,
            "grade": grade,
            "state": state,
            "technical": technical_result,
            "smc": smc_result,
            "fusion": fusion_result,
            "gemini": gemini_result,
            "trade_plan": trade_plan,
            "risk": risk_result,
        }

    # ==========================================================
    # Full Market Scan
    # ==========================================================

    def run_scan(
        self,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:

        logger.info(
            "🏗️ Building coin universe"
        )

        try:

            universe = (
                self.coin_universe
                .build_universe()
            )

        except Exception as exc:

            logger.exception(
                "Coin universe build failed: %s",
                exc,
            )

            return [
                {
                    "status": "ERROR",
                    "reason": "UNIVERSE_BUILD_FAILED",
                    "error": str(exc),
                }
            ]

        if universe is None:

            logger.warning(
                "Coin universe returned None"
            )

            return []

        if not universe:

            logger.warning(
                "Coin universe is empty"
            )

            return []

        logger.info(
            "🌎 Universe size: %s",
            len(universe),
        )

        results: List[Dict[str, Any]] = []

        # ------------------------------------------------------
        # Scan selected coins
        # ------------------------------------------------------

        selected_coins = universe[:limit]

        logger.info(
            "🔎 Scanning %s coins",
            len(selected_coins),
        )

        for index, coin in enumerate(
            selected_coins,
            start=1,
        ):

            # --------------------------------------------------
            # Support both:
            #
            # {"symbol": "BTCUSDT"}
            #
            # and
            #
            # "BTCUSDT"
            # --------------------------------------------------

            if isinstance(
                coin,
                dict,
            ):

                symbol = coin.get(
                    "symbol"
                )

            else:

                symbol = str(
                    coin
                )

            if not symbol:

                logger.warning(
                    "Skipping coin without symbol | index=%s",
                    index,
                )

                continue

            logger.info(
                "📊 Progress %s/%s | %s",
                index,
                len(selected_coins),
                symbol,
            )

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
                    "❌ Unexpected scan failure | %s",
                    symbol,
                )

                results.append(
                    {
                        "symbol": symbol,
                        "status": "ERROR",
                        "error": str(exc),
                    }
                )

        # ------------------------------------------------------
        # Summary
        # ------------------------------------------------------

        candidate_count = sum(
            1
            for item in results
            if item.get("status")
            == "CANDIDATE"
        )

        rejected_count = sum(
            1
            for item in results
            if item.get("status")
            == "REJECTED"
        )

        skipped_count = sum(
            1
            for item in results
            if item.get("status")
            == "SKIPPED"
        )

        error_count = sum(
            1
            for item in results
            if item.get("status")
            == "ERROR"
        )

        logger.info(
            "📋 Scan summary | "
            "total=%s | "
            "candidates=%s | "
            "rejected=%s | "
            "skipped=%s | "
            "errors=%s",
            len(results),
            candidate_count,
            rejected_count,
            skipped_count,
            error_count,
        )

        return results
