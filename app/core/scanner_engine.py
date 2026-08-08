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
        SMC Setup Validator
              ↓
        MTF
              ↓
        Derivatives
              ↓
        Market Context
              ↓
        Signal Fusion
              ↓
        Fusion Quality Gate
              ↓
        Gemini Review
              ↓
        Trade Plan
              ↓
        Risk Engine
              ↓
        Final Candidate

    Safety principles:

        - Never invent analysis.
        - Missing critical analysis cannot become a trade.
        - Fusion state is respected.
        - Gemini REJECT blocks the setup.
        - Gemini CAUTION does not automatically become a trade.
        - Trade-plan failure blocks the trade.
        - Risk-engine failure blocks the trade.
        - SCAN_LIMIT=0 means scan the complete universe.
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
            "validator=%s | "
            "fusion=%s | "
            "gemini=%s | "
            "trade_plan=%s | "
            "risk=%s",
            bool(self.technical_engine),
            bool(self.smc_engine),
            bool(self.mtf_engine),
            bool(self.derivatives_engine),
            bool(self.market_context_engine),
            bool(self.setup_validator),
            bool(self.fusion_engine),
            bool(self.gemini_reviewer),
            bool(self.trade_plan_engine),
            bool(self.risk_engine),
        )

    # ==========================================================
    # Helpers
    # ==========================================================

    @staticmethod
    def _safe_dict(value: Any) -> Dict[str, Any]:

        if isinstance(value, dict):
            return value

        return {}

    @staticmethod
    def _has_real_analysis(
        result: Dict[str, Any],
    ) -> bool:

        if not result:
            return False

        if str(
            result.get("status", "")
        ).upper() in {
            "ERROR",
            "FAILED",
            "SKIPPED",
        }:
            return False

        return True

    @staticmethod
    def _normalize_decision(
        result: Dict[str, Any],
    ) -> str:

        if not isinstance(result, dict):
            return "UNKNOWN"

        decision = result.get(
            "decision",
            result.get(
                "verdict",
                result.get(
                    "status",
                    "UNKNOWN",
                ),
            ),
        )

        return str(
            decision
        ).upper().strip()

    @staticmethod
    def _reject_result(
        symbol: str,
        reason: str,
        **kwargs,
    ) -> Dict[str, Any]:

        result = {
            "status": "REJECTED",
            "symbol": symbol,
            "reason": reason,
        }

        result.update(kwargs)

        return result

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

        if signature is None:

            try:

                return self._safe_dict(
                    method(context)
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

        if kwargs:

            try:

                result = method(
                    **kwargs
                )

                return self._safe_dict(
                    result
                )

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

                return self._safe_dict(
                    method(argument)
                )

            except Exception as exc:

                logger.exception(
                    "%s failed | method=%s: %s",
                    stage_name,
                    method_name,
                    exc,
                )

                return {}

        logger.warning(
            "⚠️ Could not safely invoke %s | method=%s",
            stage_name,
            method_name,
        )

        return {}

    # ==========================================================
    # SMC Setup Validation
    # ==========================================================

    def _validate_smc_setup(
        self,
        symbol: str,
        df: Any,
        technical: Dict[str, Any],
        smc: Dict[str, Any],
        mtf: Dict[str, Any],
    ) -> Dict[str, Any]:

        if self.setup_validator is None:
            return {
                "status": "SKIPPED",
                "reason": "VALIDATOR_NOT_CONFIGURED",
            }

        context = {
            "symbol": symbol,
            "df": df,
            "dataframe": df,
            "ohlcv": df,
            "technical": technical,
            "smc": smc,
            "mtf": mtf,
        }

        result = self._call_engine(
            engine=self.setup_validator,
            preferred_methods=[
                "validate",
                "evaluate",
                "analyze",
                "check",
            ],
            context=context,
            stage_name="SMC Setup Validator",
        )

        return result

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
        # 1. OHLCV
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

            return self._reject_result(
                symbol,
                "OHLCV_FETCH_FAILED",
                error=str(exc),
            )

        if df is None:

            return self._reject_result(
                symbol,
                "NO_OHLCV_DATA",
            )

        if getattr(df, "empty", True):

            return self._reject_result(
                symbol,
                "EMPTY_OHLCV",
            )

        if len(df) < 50:

            return self._reject_result(
                symbol,
                "INSUFFICIENT_CANDLES",
                candles=len(df),
            )

        logger.info(
            "OHLCV ready | %s | candles=%s",
            symbol,
            len(df),
        )

        analysis_context = {
            "symbol": symbol,
            "df": df,
            "dataframe": df,
            "ohlcv": df,
        }

        # ------------------------------------------------------
        # 2. Technical
        # ------------------------------------------------------

        technical_result = {}

        if self.technical_engine:

            try:

                technical_result = self._safe_dict(
                    self.technical_engine.analyze(
                        df
                    )
                )

            except Exception as exc:

                logger.exception(
                    "Technical analysis failed | %s: %s",
                    symbol,
                    exc,
                )

        analysis_context[
            "technical"
        ] = technical_result

        # ------------------------------------------------------
        # 3. SMC
        # ------------------------------------------------------

        smc_result = {}

        if self.smc_engine:

            try:

                smc_result = self._safe_dict(
                    self.smc_engine.analyze(
                        df
                    )
                )

            except Exception as exc:

                logger.exception(
                    "SMC analysis failed | %s: %s",
                    symbol,
                    exc,
                )

        analysis_context[
            "smc"
        ] = smc_result

        # ------------------------------------------------------
        # Safety gate
        # ------------------------------------------------------

        if not self._has_real_analysis(
            technical_result
        ) and not self._has_real_analysis(
            smc_result
        ):

            return self._reject_result(
                symbol,
                "NO_ANALYSIS_DATA",
            )

        # ------------------------------------------------------
        # 4. SMC Setup Validator
        # ------------------------------------------------------

        validator_result = (
            self._validate_smc_setup(
                symbol=symbol,
                df=df,
                technical=technical_result,
                smc=smc_result,
                mtf={},
            )
        )

        analysis_context[
            "setup_validation"
        ] = validator_result

        validator_decision = (
            self._normalize_decision(
                validator_result
            )
        )

        if validator_decision in {
            "REJECT",
            "REJECTED",
            "NO_TRADE",
            "INVALID",
            "BLOCK",
            "BLOCKED",
        }:

            logger.info(
                "❌ SMC setup validator rejected | %s",
                symbol,
            )

            return self._reject_result(
                symbol,
                "SMC_SETUP_VALIDATION",
                technical=technical_result,
                smc=smc_result,
                setup_validation=validator_result,
            )

        # ------------------------------------------------------
        # 5. MTF
        # ------------------------------------------------------

        mtf_result = {}

        if self.mtf_engine:

            mtf_result = self._call_engine(
                engine=self.mtf_engine,
                preferred_methods=[
                    "evaluate",
                    "analyze",
                ],
                context=dict(
                    analysis_context
                ),
                stage_name="MTF",
            )

        analysis_context[
            "mtf"
        ] = mtf_result

        # ------------------------------------------------------
        # 6. Derivatives
        # ------------------------------------------------------

        derivatives_result = {}

        if self.derivatives_engine:

            derivatives_result = self._call_engine(
                engine=self.derivatives_engine,
                preferred_methods=[
                    "analyze",
                    "evaluate",
                ],
                context=dict(
                    analysis_context
                ),
                stage_name="Derivatives",
            )

        analysis_context[
            "derivatives"
        ] = derivatives_result

        # ------------------------------------------------------
        # 7. Market Context
        # ------------------------------------------------------

        market_result = {}

        if self.market_context_engine:

            try:

                market_result = self._safe_dict(
                    self.market_context_engine.analyze(
                        symbol
                    )
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
        # 8. Signal Fusion
        # ------------------------------------------------------

        if self.fusion_engine is None:

            return self._reject_result(
                symbol,
                "NO_FUSION_ENGINE",
                technical=technical_result,
                smc=smc_result,
                mtf=mtf_result,
                derivatives=derivatives_result,
                market=market_result,
            )

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

            return self._reject_result(
                symbol,
                "FUSION_FAILED",
                error=str(exc),
            )

        try:

            score = float(
                fusion_result.get(
                    "score",
                    0,
                ) or 0
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

        state = str(
            fusion_result.get(
                "state",
                "NO_CLEAR_SETUP",
            )
        ).upper()

        confluence = float(
            fusion_result.get(
                "confluence",
                0,
            ) or 0
        )

        logger.info(
            "Fusion | %s | direction=%s | score=%.2f | "
            "grade=%s | state=%s | confluence=%.2f%%",
            symbol,
            direction,
            score,
            grade,
            state,
            confluence,
        )

        # ------------------------------------------------------
        # 9. Score Gate
        # ------------------------------------------------------

        try:

            minimum_score = float(
                os.getenv(
                    "MIN_SIGNAL_SCORE",
                    os.getenv(
                        "SCAN_MIN_SCORE",
                        "70",
                    ),
                )
            )

        except (
            TypeError,
            ValueError,
        ):

            minimum_score = 70.0

        if score < minimum_score:

            return self._reject_result(
                symbol,
                "QUALITY_GATE",
                score=score,
                direction=direction,
                grade=grade,
                state=state,
                confluence=confluence,
                fusion=fusion_result,
            )

        # ------------------------------------------------------
        # 10. Direction Gate
        # ------------------------------------------------------

        if direction not in {
            "BULLISH",
            "BEARISH",
        }:

            return self._reject_result(
                symbol,
                "NEUTRAL_DIRECTION",
                score=score,
                direction=direction,
                grade=grade,
                state=state,
                confluence=confluence,
                fusion=fusion_result,
            )

        # ------------------------------------------------------
        # 11. Fusion State Gate
        # ------------------------------------------------------

        if state not in {
            "TRADE_CANDIDATE",
            "WATCH",
        }:

            return self._reject_result(
                symbol,
                "FUSION_STATE_REJECTED",
                score=score,
                direction=direction,
                grade=grade,
                state=state,
                confluence=confluence,
                fusion=fusion_result,
            )

        # ------------------------------------------------------
        # WATCH is not a trade candidate.
        #
        # It can continue to Gemini only as a review,
        # but cannot become FINAL CANDIDATE unless Gemini
        # confirms and confluence is strong enough.
        # ------------------------------------------------------

        # ------------------------------------------------------
        # 12. Gemini Review
        # ------------------------------------------------------

        gemini_result = {}

        if self.gemini_reviewer:

            review_payload = {
                "symbol": symbol,
                "technical": technical_result,
                "smc": smc_result,
                "mtf": mtf_result,
                "derivatives": derivatives_result,
                "market": market_result,
                "setup_validation": validator_result,
                "fusion": fusion_result,
            }

            try:

                gemini_result = self._safe_dict(
                    self.gemini_reviewer.review(
                        review_payload
                    )
                )

            except Exception as exc:

                logger.exception(
                    "Gemini review failed | %s: %s",
                    symbol,
                    exc,
                )

                return self._reject_result(
                    symbol,
                    "GEMINI_REVIEW_FAILED",
                    error=str(exc),
                    fusion=fusion_result,
                )

        else:

            # No reviewer means no production trade approval.
            gemini_result = {
                "status": "SKIPPED",
                "decision": "UNKNOWN",
                "reason": "GEMINI_NOT_CONFIGURED",
            }

        gemini_decision = (
            self._normalize_decision(
                gemini_result
            )
        )

        # ------------------------------------------------------
        # Gemini must explicitly CONFIRM
        # ------------------------------------------------------

        if gemini_decision in {
            "REJECT",
            "REJECTED",
            "NO_TRADE",
        }:

            return self._reject_result(
                symbol,
                "GEMINI_REJECTION",
                score=score,
                direction=direction,
                grade=grade,
                state=state,
                confluence=confluence,
                fusion=fusion_result,
                gemini=gemini_result,
            )

        if gemini_decision != "CONFIRM":

            return self._reject_result(
                symbol,
                "GEMINI_NOT_CONFIRMED",
                score=score,
                direction=direction,
                grade=grade,
                state=state,
                confluence=confluence,
                fusion=fusion_result,
                gemini=gemini_result,
            )

        # ------------------------------------------------------
        # 13. Final trade-quality confluence gate
        # ------------------------------------------------------

        if confluence < 70:

            return self._reject_result(
                symbol,
                "INSUFFICIENT_CONFLUENCE",
                score=score,
                direction=direction,
                grade=grade,
                state=state,
                confluence=confluence,
                fusion=fusion_result,
                gemini=gemini_result,
            )

        # ------------------------------------------------------
        # 14. Trade Plan
        # ------------------------------------------------------

        if self.trade_plan_engine is None:

            return self._reject_result(
                symbol,
                "TRADE_PLAN_ENGINE_UNAVAILABLE",
                fusion=fusion_result,
                gemini=gemini_result,
            )

        try:

            trade_plan = self._safe_dict(
                self.trade_plan_engine.build(
                    symbol=symbol,
                    dataframe=df,
                    fusion_result=fusion_result,
                    gemini_result=gemini_result,
                )
            )

        except Exception as exc:

            logger.exception(
                "Trade plan failed | %s: %s",
                symbol,
                exc,
            )

            return self._reject_result(
                symbol,
                "TRADE_PLAN_FAILED",
                error=str(exc),
                fusion=fusion_result,
                gemini=gemini_result,
            )

        if not trade_plan:

            return self._reject_result(
                symbol,
                "EMPTY_TRADE_PLAN",
                fusion=fusion_result,
                gemini=gemini_result,
            )

        if str(
            trade_plan.get(
                "status",
                "SUCCESS",
            )
        ).upper() in {
            "ERROR",
            "FAILED",
            "INVALID",
            "REJECTED",
            "BLOCKED",
        }:

            return self._reject_result(
                symbol,
                "INVALID_TRADE_PLAN",
                fusion=fusion_result,
                gemini=gemini_result,
                trade_plan=trade_plan,
            )

        # ------------------------------------------------------
        # 15. Risk Engine
        # ------------------------------------------------------

        if self.risk_engine is None:

            return self._reject_result(
                symbol,
                "RISK_ENGINE_UNAVAILABLE",
                fusion=fusion_result,
                gemini=gemini_result,
                trade_plan=trade_plan,
            )

        try:

            risk_result = self._safe_dict(
                self.risk_engine.evaluate(
                    symbol=symbol,
                    fusion_result=fusion_result,
                    gemini_result=gemini_result,
                    trade_plan=trade_plan,
                )
            )

        except Exception as exc:

            logger.exception(
                "Risk evaluation failed | %s: %s",
                symbol,
                exc,
            )

            return self._reject_result(
                symbol,
                "RISK_ENGINE_FAILED",
                error=str(exc),
                fusion=fusion_result,
                gemini=gemini_result,
                trade_plan=trade_plan,
            )

        if not risk_result:

            return self._reject_result(
                symbol,
                "EMPTY_RISK_RESULT",
                fusion=fusion_result,
                gemini=gemini_result,
                trade_plan=trade_plan,
            )

        risk_decision = (
            self._normalize_decision(
                risk_result
            )
        )

        if risk_decision in {
            "REJECT",
            "REJECTED",
            "NO_TRADE",
            "BLOCK",
            "BLOCKED",
            "INVALID",
        }:

            return self._reject_result(
                symbol,
                "RISK_ENGINE",
                score=score,
                direction=direction,
                grade=grade,
                state=state,
                confluence=confluence,
                fusion=fusion_result,
                gemini=gemini_result,
                trade_plan=trade_plan,
                risk=risk_result,
            )

        # ------------------------------------------------------
        # Risk engine must explicitly approve.
        # ------------------------------------------------------

        if risk_decision not in {
            "APPROVE",
            "APPROVED",
            "PASS",
            "PASSED",
            "SUCCESS",
        }:

            return self._reject_result(
                symbol,
                "RISK_NOT_EXPLICITLY_APPROVED",
                score=score,
                direction=direction,
                grade=grade,
                state=state,
                confluence=confluence,
                fusion=fusion_result,
                gemini=gemini_result,
                trade_plan=trade_plan,
                risk=risk_result,
            )

        # ------------------------------------------------------
        # 16. FINAL CANDIDATE
        # ------------------------------------------------------

        logger.info(
            "🎯 FINAL CANDIDATE | %s | "
            "score=%.2f | direction=%s | "
            "confluence=%.2f%%",
            symbol,
            score,
            direction,
            confluence,
        )

        return {
            "status": "CANDIDATE",
            "symbol": symbol,
            "score": score,
            "direction": direction,
            "grade": grade,
            "state": state,
            "confluence": confluence,
            "technical": technical_result,
            "smc": smc_result,
            "setup_validation": validator_result,
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

        # ------------------------------------------------------
        # FIX:
        #
        # limit = 0 means COMPLETE UNIVERSE.
        # ------------------------------------------------------

        if limit < 0:
            limit = 0

        logger.info(
            "🎯 Scan limit: %s",
            (
                "FULL UNIVERSE"
                if limit == 0
                else limit
            ),
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

        # ------------------------------------------------------
        # FIX:
        #
        # 0 = all coins.
        # ------------------------------------------------------

        if limit == 0:

            selected_coins = universe

        else:

            selected_coins = universe[
                :limit
            ]

        logger.info(
            "🔎 Scanning %s coins",
            len(selected_coins),
        )

        results: List[
            Dict[str, Any]
        ] = []

        # ------------------------------------------------------
        # Scan
        # ------------------------------------------------------

        for index, coin in enumerate(
            selected_coins,
            start=1,
        ):

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
