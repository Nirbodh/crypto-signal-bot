import inspect
import logging
import os
from typing import Any, Dict, List, Optional


logger = logging.getLogger("crypto-signal-bot")


class ScannerEngine:
    """
    Production Scanner / Orchestration Engine.

    Pipeline:

        Coin Universe
              ↓
        OHLCV
              ↓
        Technical
              ↓
        SMC
              ↓
        MTF
              ↓
        Derivatives
              ↓
        Market Context
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

    IMPORTANT:

    This class orchestrates the system.

    It does NOT invent market data.

    If an analysis engine cannot be executed with valid
    market context, that component remains unavailable
    instead of receiving an empty `{}` payload and producing
    a misleading result.
    """

    # ==========================================================
    # Initialization
    # ==========================================================

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
            "mtf=%s | "
            "derivatives=%s | "
            "market=%s | "
            "fusion=%s | "
            "gemini=%s | "
            "risk=%s",
            bool(self.technical_engine),
            bool(self.smc_engine),
            bool(self.mtf_engine),
            bool(self.derivatives_engine),
            bool(self.market_context_engine),
            bool(self.fusion_engine),
            bool(self.gemini_reviewer),
            bool(self.risk_engine),
        )

    # ==========================================================
    # Helpers
    # ==========================================================

    @staticmethod
    def _safe_dict(value: Any) -> Dict[str, Any]:
        """
        Convert an engine result into a safe dictionary.

        None / invalid results become {}.

        We intentionally DO NOT create fake scores.
        """

        if isinstance(value, dict):
            return value

        return {}

    @staticmethod
    def _has_real_analysis(
        result: Dict[str, Any],
    ) -> bool:
        """
        Determine whether an analysis result contains
        meaningful information.

        Empty dictionaries are never considered valid analysis.
        """

        if not result:
            return False

        if result.get("status") in {
            "ERROR",
            "FAILED",
            "SKIPPED",
        }:
            return False

        return True

    @staticmethod
    def _contains_direction(
        result: Dict[str, Any],
    ) -> bool:

        direction = str(
            result.get(
                "direction",
                result.get(
                    "trend",
                    result.get(
                        "preferred_direction",
                        "",
                    ),
                ),
            )
        ).upper()

        return direction in {
            "BULLISH",
            "BEARISH",
            "NEUTRAL",
        }

    # ==========================================================
    # Flexible Engine Invocation
    # ==========================================================

    def _call_engine(
        self,
        engine: Any,
        preferred_methods: List[str],
        context: Dict[str, Any],
        stage_name: str,
    ) -> Dict[str, Any]:
        """
        Safely call an analysis engine without sending `{}`.

        The method signature is inspected so that engines using
        slightly different argument names can still receive the
        correct real market context.

        IMPORTANT:

        If no compatible method can be found, we return {}
        instead of fabricating analysis.
        """

        if engine is None:
            return {}

        method = None
        method_name = None

        for name in preferred_methods:

            candidate = getattr(
                engine,
                name,
                None,
            )

            if callable(candidate):

                method = candidate
                method_name = name
                break

        if method is None:

            logger.warning(
                "⚠️ %s engine has no supported method | methods=%s",
                stage_name,
                preferred_methods,
            )

            return {}

        try:

            signature = inspect.signature(
                method
            )

        except (
            TypeError,
            ValueError,
        ):

            signature = None

        # ------------------------------------------------------
        # If signature is unavailable, use a rich context object.
        # ------------------------------------------------------

        if signature is None:

            try:

                result = method(
                    context
                )

                return self._safe_dict(
                    result
                )

            except Exception as exc:

                logger.exception(
                    "%s failed | %s: %s",
                    stage_name,
                    method_name,
                    exc,
                )

                return {}

        parameters = list(
            signature.parameters.values()
        )

        positional_required = [
            parameter
            for parameter in parameters
            if (
                parameter.kind
                in (
                    inspect.Parameter.POSITIONAL_ONLY,
                    inspect.Parameter.POSITIONAL_OR_KEYWORD,
                )
                and parameter.default
                is inspect.Parameter.empty
            )
        ]

        keyword_parameters = {
            parameter.name: parameter
            for parameter in parameters
            if parameter.kind
            in (
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
                inspect.Parameter.KEYWORD_ONLY,
            )
        }

        # ------------------------------------------------------
        # Common parameter aliases.
        # ------------------------------------------------------

        aliases = {
            "symbol": [
                "symbol",
                "pair",
                "asset",
            ],
            "df": [
                "df",
                "dataframe",
                "ohlcv",
                "candles",
                "price_data",
            ],
            "data": [
                "data",
                "context",
                "market_data",
                "analysis_data",
            ],
            "technical": [
                "technical",
                "technical_result",
                "technical_analysis",
            ],
            "smc": [
                "smc",
                "smc_result",
                "smc_analysis",
            ],
            "mtf": [
                "mtf",
                "mtf_result",
                "mtf_analysis",
            ],
            "derivatives": [
                "derivatives",
                "derivatives_result",
                "derivatives_analysis",
            ],
            "market": [
                "market",
                "market_result",
                "market_context",
            ],
        }

        kwargs: Dict[str, Any] = {}

        for context_key, names in aliases.items():

            if context_key not in context:
                continue

            for name in names:

                if name in keyword_parameters:

                    kwargs[name] = context[
                        context_key
                    ]

                    break

        # ------------------------------------------------------
        # If method accepts **kwargs, send full context.
        # ------------------------------------------------------

        accepts_kwargs = any(
            parameter.kind
            == inspect.Parameter.VAR_KEYWORD
            for parameter in parameters
        )

        if accepts_kwargs:

            for key, value in context.items():

                kwargs.setdefault(
                    key,
                    value,
                )

        # ------------------------------------------------------
        # Try keyword invocation when possible.
        # ------------------------------------------------------

        if kwargs:

            try:

                result = method(
                    **kwargs
                )

                result = self._safe_dict(
                    result
                )

                if result:

                    return result

                logger.warning(
                    "⚠️ %s returned empty result | method=%s",
                    stage_name,
                    method_name,
                )

                return {}

            except TypeError as exc:

                logger.warning(
                    "⚠️ %s keyword invocation incompatible | "
                    "method=%s | %s",
                    stage_name,
                    method_name,
                    exc,
                )

            except Exception as exc:

                logger.exception(
                    "%s failed | method=%s: %s",
                    stage_name,
                    method_name,
                    exc,
                )

                return {}

        # ------------------------------------------------------
        # Single required argument fallback.
        #
        # We pass a rich context object, NOT `{}`.
        # ------------------------------------------------------

        if len(positional_required) == 1:

            parameter_name = (
                positional_required[0].name.lower()
            )

            if parameter_name in {
                "df",
                "dataframe",
                "ohlcv",
                "candles",
                "price_data",
            }:

                argument = context.get(
                    "df"
                )

            elif parameter_name in {
                "symbol",
                "pair",
                "asset",
            }:

                argument = context.get(
                    "symbol"
                )

            else:

                argument = context

            try:

                result = method(
                    argument
                )

                return self._safe_dict(
                    result
                )

            except Exception as exc:

                logger.exception(
                    "%s failed | method=%s: %s",
                    stage_name,
                    method_name,
                    exc,
                )

                return {}

        # ------------------------------------------------------
        # No usable invocation.
        # ------------------------------------------------------

        logger.warning(
            "⚠️ Could not safely invoke %s | method=%s",
            stage_name,
            method_name,
        )

        return {}

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
                limit=350,
            )

        except Exception as exc:

            logger.warning(
                "OHLCV fetch failed | %s: %s",
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
        # Shared analysis context
        # ------------------------------------------------------

        analysis_context: Dict[str, Any] = {
            "symbol": symbol,
            "df": df,
            "dataframe": df,
            "ohlcv": df,
        }

        # ------------------------------------------------------
        # 2. Technical Analysis
        # ------------------------------------------------------

        technical_result: Dict[str, Any] = {}

        if self.technical_engine:

            try:

                technical_result = self._safe_dict(
                    self.technical_engine.analyze(
                        df
                    )
                )

                if technical_result:

                    logger.info(
                        "Technical analysis complete | %s",
                        symbol,
                    )

                else:

                    logger.warning(
                        "⚠️ Technical analysis empty | %s",
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

        analysis_context[
            "technical"
        ] = technical_result

        # ------------------------------------------------------
        # 3. SMC Analysis
        # ------------------------------------------------------

        smc_result: Dict[str, Any] = {}

        if self.smc_engine:

            try:

                smc_result = self._safe_dict(
                    self.smc_engine.analyze(
                        df
                    )
                )

                if smc_result:

                    logger.info(
                        "SMC analysis complete | %s",
                        symbol,
                    )

                else:

                    logger.warning(
                        "⚠️ SMC analysis empty | %s",
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

        analysis_context[
            "smc"
        ] = smc_result

        # ------------------------------------------------------
        # 4. MTF Analysis
        # ------------------------------------------------------
        #
        # FIX:
        # Previous code:
        #
        #     mtf_engine.evaluate({})
        #
        # That was invalid because no market data was supplied.
        #
        # Now the engine receives symbol + OHLCV + existing
        # analysis context.
        # ------------------------------------------------------

        mtf_result: Dict[str, Any] = {}

        if self.mtf_engine:

            mtf_context = dict(
                analysis_context
            )

            mtf_result = self._call_engine(
                engine=self.mtf_engine,
                preferred_methods=[
                    "evaluate",
                    "analyze",
                ],
                context=mtf_context,
                stage_name="MTF",
            )

            if mtf_result:

                logger.info(
                    "MTF analysis complete | %s",
                    symbol,
                )

            else:

                logger.warning(
                    "⚠️ MTF analysis unavailable | %s",
                    symbol,
                )

        analysis_context[
            "mtf"
        ] = mtf_result

        # ------------------------------------------------------
        # 5. Derivatives Analysis
        # ------------------------------------------------------
        #
        # FIX:
        # Previous code:
        #
        #     derivatives_engine.analyze({})
        #
        # That was invalid.
        #
        # Now the engine receives actual symbol + OHLCV context.
        # ------------------------------------------------------

        derivatives_result: Dict[str, Any] = {}

        if self.derivatives_engine:

            derivatives_context = dict(
                analysis_context
            )

            derivatives_result = self._call_engine(
                engine=self.derivatives_engine,
                preferred_methods=[
                    "analyze",
                    "evaluate",
                ],
                context=derivatives_context,
                stage_name="Derivatives",
            )

            if derivatives_result:

                logger.info(
                    "Derivatives analysis complete | %s",
                    symbol,
                )

            else:

                logger.warning(
                    "⚠️ Derivatives analysis unavailable | %s",
                    symbol,
                )

        analysis_context[
            "derivatives"
        ] = derivatives_result

        # ------------------------------------------------------
        # 6. Market Context
        # ------------------------------------------------------

        market_result: Dict[str, Any] = {}

        if self.market_context_engine:

            try:

                market_result = self._safe_dict(
                    self.market_context_engine.analyze(
                        symbol
                    )
                )

                if market_result:

                    logger.info(
                        "Market context complete | %s",
                        symbol,
                    )

                else:

                    logger.warning(
                        "⚠️ Market context empty | %s",
                        symbol,
                    )

            except Exception as exc:

                logger.exception(
                    "Market context failed | %s: %s",
                    symbol,
                    exc,
                )

        analysis_context[
            "market"
        ] = market_result

        # ------------------------------------------------------
        # Safety Gate
        # ------------------------------------------------------

        if (
            not self._has_real_analysis(
                technical_result
            )
            and not self._has_real_analysis(
                smc_result
            )
        ):

            logger.warning(
                "No valid technical/SMC data available | %s",
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

                fusion_result = self._safe_dict(
                    self.fusion_engine.evaluate(
                        technical=technical_result,
                        smc=smc_result,
                        mtf=mtf_result,
                        derivatives=derivatives_result,
                        market=market_result,
                    )
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
                    "mtf": mtf_result,
                    "derivatives": derivatives_result,
                    "market": market_result,
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

        try:

            score = float(
                fusion_result.get(
                    "score",
                    0,
                )
                or 0
            )

        except (
            TypeError,
            ValueError,
        ):

            score = 0.0

        direction = str(
            fusion_result.get(
                "direction",
                "NEUTRAL",
            )
        ).upper()

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
            "state=%s | "
            "confluence=%s",
            symbol,
            direction,
            score,
            grade,
            state,
            fusion_result.get(
                "confluence",
                0,
            ),
        )

        # ------------------------------------------------------
        # 8. Quality Gate
        # ------------------------------------------------------
        #
        # Keep this gate BEFORE Gemini to save API cost.
        #
        # SCAN_MIN_SCORE can be changed through environment.
        #

        try:

            minimum_score = float(
                os.getenv(
                    "SCAN_MIN_SCORE",
                    "70",
                )
            )

        except (
            TypeError,
            ValueError,
        ):

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
                "mtf": mtf_result,
                "derivatives": derivatives_result,
                "market": market_result,
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
                "mtf": mtf_result,
                "derivatives": derivatives_result,
                "market": market_result,
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
                    "mtf": mtf_result,
                    "derivatives": derivatives_result,
                    "market": market_result,
                    "fusion": fusion_result,
                }

                gemini_result = self._safe_dict(
                    self.gemini_reviewer.review(
                        review_payload
                    )
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
        # Gemini Decision Gate
        # ------------------------------------------------------

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
                "mtf": mtf_result,
                "derivatives": derivatives_result,
                "market": market_result,
                "fusion": fusion_result,
                "gemini": gemini_result,
                "reason": "GEMINI_REJECTION",
            }

        # ------------------------------------------------------
        # 10. Trade Plan
        # ------------------------------------------------------

        trade_plan: Dict[str, Any] = {}

        if self.trade_plan_engine:

            try:

                trade_plan = self._safe_dict(
                    self.trade_plan_engine.build(
                        symbol=symbol,
                        dataframe=df,
                        fusion_result=fusion_result,
                        gemini_result=gemini_result,
                    )
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
        # 11. Risk Engine
        # ------------------------------------------------------

        risk_result: Dict[str, Any] = {}

        if self.risk_engine:

            try:

                risk_result = self._safe_dict(
                    self.risk_engine.evaluate(
                        symbol=symbol,
                        fusion_result=fusion_result,
                        gemini_result=gemini_result,
                        trade_plan=trade_plan,
                    )
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
        # 12. Final Risk Gate
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
                "mtf": mtf_result,
                "derivatives": derivatives_result,
                "market": market_result,
                "fusion": fusion_result,
                "gemini": gemini_result,
                "trade_plan": trade_plan,
                "risk": risk_result,
                "reason": "RISK_ENGINE",
            }

        # ------------------------------------------------------
        # 13. FINAL CANDIDATE
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
            "mtf": mtf_result,
            "derivatives": derivatives_result,
            "market": market_result,
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
        limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:

        logger.info(
            "🏗️ Building coin universe"
        )

        # ------------------------------------------------------
        # Scan limit
        # ------------------------------------------------------

        if limit is None:

            try:

                limit = int(
                    os.getenv(
                        "SCAN_LIMIT",
                        "100",
                    )
                )

            except (
                TypeError,
                ValueError,
            ):

                limit = 100

        if limit < 1:

            limit = 1

        logger.info(
            "🎯 Scan limit: %s",
            limit,
        )

        # ------------------------------------------------------
        # Build Universe
        # ------------------------------------------------------

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

        results: List[
            Dict[str, Any]
        ] = []

        # ------------------------------------------------------
        # Select coins
        # ------------------------------------------------------

        selected_coins = universe[
            :limit
        ]

        logger.info(
            "🔎 Scanning %s coins",
            len(selected_coins),
        )

        # ------------------------------------------------------
        # Scan
        # ------------------------------------------------------

        for index, coin in enumerate(
            selected_coins,
            start=1,
        ):

            # --------------------------------------------------
            # Support:
            #
            # {"symbol": "BTCUSDT"}
            #
            # and:
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

            symbol = str(
                symbol
            ).strip().upper()

            logger.info(
                "📊 Progress %s/%s | %s",
                index,
                len(selected_coins),
                symbol,
            )

            try:

                result = self.scan_symbol(
                    symbol
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
