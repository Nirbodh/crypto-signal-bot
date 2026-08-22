import inspect
import logging
import os
import time
from typing import Any, Dict, List, Optional


logger = logging.getLogger("crypto-signal-bot")


class ScannerEngine:
    """
    Production Scanner / Orchestration Engine.

    Pipeline:

        Coin Universe
              ↓
        OHLCV 4H / 1H / 15m / 5m
              ↓
        Technical
              ↓
        SMC
              ↓
        Multi-Timeframe
              ↓
        Derivatives
              ↓
        Market Context
              ↓
        Signal Fusion
              ↓
        Minimum Evidence Gate
              ↓
        Fusion State Gate
              ↓
        Gemini Review (optional)
              ↓
        Trade Plan (optional)
              ↓
        Risk Engine (optional)
              ↓
        Final Candidate

    IMPORTANT
    ---------
    This engine orchestrates analysis.

    It does NOT invent:
        - OHLCV
        - technical scores
        - SMC scores
        - MTF scores
        - derivatives data
        - market data
        - AI decisions

    Missing data remains missing.

    The Scanner is intentionally conservative:
        - score alone is not enough
        - direction alone is not enough
        - confluence matters
        - minimum evidence matters
        - Gemini is a reviewer, not the primary signal
        - Risk Engine has final veto authority when configured
    """

    TIMEFRAMES = (
        "4h",
        "1h",
        "15m",
        "5m",
    )

    # ----------------------------------------------------------
    # Minimum candles requested from the data provider.
    #
    # MTF currently requires 120 valid candles.
    # 350 gives enough room for EMA100 + indicator warmup.
    # ----------------------------------------------------------

    OHLCV_LIMIT = 350

    # ----------------------------------------------------------
    # Minimum evidence for a meaningful setup.
    #
    # Technical + SMC are the core setup engines.
    # MTF is strongly preferred but may be PARTIAL.
    # ----------------------------------------------------------

    MIN_CORE_COMPONENTS = 2

    # ----------------------------------------------------------
    # Preferred minimum confluence.
    #
    # SignalFusionEngine itself determines state, but Scanner
    # applies this as an additional safety layer.
    # ----------------------------------------------------------

    MIN_TRADE_CONFLUENCE = 70.0
    MIN_WATCH_CONFLUENCE = 60.0

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

        # 🔥 NEW: Breakout Memory for retest detection
        self.breakout_memory = {}  # symbol → {"level": float, "time": str, "direction": str, "level_type": str}

        logger.info(
            "ScannerEngine initialized | "
            "technical=%s | smc=%s | mtf=%s | "
            "derivatives=%s | market=%s | "
            "fusion=%s | gemini=%s | "
            "trade_plan=%s | risk=%s",
            bool(self.technical_engine),
            bool(self.smc_engine),
            bool(self.mtf_engine),
            bool(self.derivatives_engine),
            bool(self.market_context_engine),
            bool(self.fusion_engine),
            bool(self.gemini_reviewer),
            bool(self.trade_plan_engine),
            bool(self.risk_engine),
        )

    # ==========================================================
    # Generic Helpers
    # ==========================================================

    @staticmethod
    def _safe_dict(
        value: Any,
    ) -> Dict[str, Any]:

        if isinstance(value, dict):
            return value

        return {}

    @staticmethod
    def _normalize_direction(
        value: Any,
    ) -> str:

        direction = str(
            value or "NEUTRAL"
        ).upper().strip()

        if direction in {
            "BULLISH",
            "BEARISH",
            "NEUTRAL",
        }:
            return direction

        if direction in {
            "LONG",
            "BUY",
        }:
            return "BULLISH"

        if direction in {
            "SHORT",
            "SELL",
        }:
            return "BEARISH"

        return "NEUTRAL"

    @staticmethod
    def _to_float(
        value: Any,
    ) -> Optional[float]:

        try:
            return float(value)
        except (
            TypeError,
            ValueError,
        ):
            return None

    @classmethod
    def _has_real_analysis(
        cls,
        result: Dict[str, Any],
    ) -> bool:

        if not isinstance(result, dict):
            return False

        if not result:
            return False

        status = str(
            result.get(
                "status",
                "",
            )
        ).upper()

        if status in {
            "ERROR",
            "FAILED",
            "SKIPPED",
            "UNAVAILABLE",
        }:
            return False

        # MTF may return PARTIAL and still contain real data.
        if status == "PARTIAL":
            return True

        return True

    @classmethod
    def _has_numeric_score(
        cls,
        result: Dict[str, Any],
    ) -> bool:

        if not cls._has_real_analysis(result):
            return False

        return (
            cls._to_float(
                result.get("score")
            )
            is not None
        )

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

        # ------------------------------------------------------
        # No signature available
        # ------------------------------------------------------

        if signature is None:

            try:

                result = method(context)

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

            "timeframe_data": [
                "timeframe_data",
                "timeframes",
                "multi_timeframe_data",
            ],
        }

        kwargs = {}

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

        # ------------------------------------------------------
        # Keyword invocation
        # ------------------------------------------------------

        if kwargs:

            try:

                result = method(
                    **kwargs
                )

                return self._safe_dict(
                    result
                )

            except TypeError as exc:

                logger.debug(
                    "%s keyword invocation incompatible | "
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
        # Single required argument fallback
        # ------------------------------------------------------

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

        if len(positional_required) == 1:

            parameter_name = (
                positional_required[0]
                .name
                .lower()
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

            elif parameter_name in {
                "timeframe_data",
                "timeframes",
            }:

                argument = context.get(
                    "timeframe_data",
                    {},
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

        logger.warning(
            "⚠️ Could not safely invoke %s | method=%s",
            stage_name,
            method_name,
        )

        return {}

    # ==========================================================
    # OHLCV Fetch
    # ==========================================================

    def _fetch_timeframe(
        self,
        symbol: str,
        timeframe: str,
        limit: int = OHLCV_LIMIT,
    ):

        if self.ohlcv_fetcher is None:

            logger.error(
                "OHLCV fetcher is not configured"
            )

            return None

        try:

            fetch_method = getattr(
                self.ohlcv_fetcher,
                "fetch",
                None,
            )

            if not callable(
                fetch_method
            ):

                # Compatibility with alternative fetcher names.
                for name in (
                    "fetch_ohlcv",
                    "get_ohlcv",
                    "get_candles",
                ):

                    candidate = getattr(
                        self.ohlcv_fetcher,
                        name,
                        None,
                    )

                    if callable(candidate):

                        fetch_method = candidate
                        break

            if not callable(
                fetch_method
            ):

                logger.error(
                    "OHLCV fetcher has no supported fetch method"
                )

                return None

            signature = inspect.signature(
                fetch_method
            )

            parameters = signature.parameters

            kwargs = {}

            # --------------------------------------------------
            # Symbol
            # --------------------------------------------------

            if "symbol" in parameters:

                kwargs["symbol"] = symbol

            elif "pair" in parameters:

                kwargs["pair"] = symbol

            elif "asset" in parameters:

                kwargs["asset"] = symbol

            # --------------------------------------------------
            # Timeframe
            # --------------------------------------------------

            if "timeframe" in parameters:

                kwargs["timeframe"] = timeframe

            elif "tf" in parameters:

                kwargs["tf"] = timeframe

            elif "interval" in parameters:

                kwargs["interval"] = timeframe

            # --------------------------------------------------
            # Limit
            # --------------------------------------------------

            if "limit" in parameters:

                kwargs["limit"] = limit

            elif "candles" in parameters:

                kwargs["candles"] = limit

            elif "count" in parameters:

                kwargs["count"] = limit

            # --------------------------------------------------
            # Execute
            # --------------------------------------------------

            df = fetch_method(
                **kwargs
            )

            return df

        except TypeError:

            # --------------------------------------------------
            # Positional fallback
            # --------------------------------------------------

            try:

                return fetch_method(
                    symbol,
                    timeframe,
                    limit,
                )

            except Exception as exc:

                logger.warning(
                    "OHLCV positional fetch failed | "
                    "%s | %s | %s",
                    symbol,
                    timeframe,
                    exc,
                )

                return None

        except Exception as exc:

            logger.warning(
                "OHLCV fetch failed | "
                "%s | timeframe=%s | %s",
                symbol,
                timeframe,
                exc,
            )

            return None

    # ==========================================================
    # Fetch All Timeframes
    # ==========================================================

    def _fetch_all_timeframes(
        self,
        symbol: str,
    ) -> Dict[str, Any]:

        timeframe_data = {}

        for timeframe in self.TIMEFRAMES:

            df = self._fetch_timeframe(
                symbol=symbol,
                timeframe=timeframe,
                limit=self.OHLCV_LIMIT,
            )

            if df is None:

                logger.warning(
                    "⚠️ Missing OHLCV | %s | %s",
                    symbol,
                    timeframe,
                )

                timeframe_data[
                    timeframe
                ] = None

                continue

            if getattr(
                df,
                "empty",
                True,
            ):

                logger.warning(
                    "⚠️ Empty OHLCV | %s | %s",
                    symbol,
                    timeframe,
                )

                timeframe_data[
                    timeframe
                ] = None

                continue

            timeframe_data[
                timeframe
            ] = df

            logger.info(
                "OHLCV ready | %s | %s | candles=%s",
                symbol,
                timeframe,
                len(df),
            )

        return timeframe_data

    # ==========================================================
    # Minimum Evidence Gate
    # ==========================================================

    def _minimum_evidence_gate(
        self,
        technical: Dict[str, Any],
        smc: Dict[str, Any],
        mtf: Dict[str, Any],
        derivatives: Dict[str, Any],
        fusion: Dict[str, Any],
    ) -> Dict[str, Any]:

        core_components = []

        for name, result in (
            ("technical", technical),
            ("smc", smc),
            ("mtf", mtf),
            ("derivatives", derivatives),
        ):

            if self._has_numeric_score(
                result
            ):

                core_components.append(
                    name
                )

        # Technical + SMC are the primary setup evidence.
        core_setup_components = []

        if self._has_numeric_score(
            technical
        ):
            core_setup_components.append(
                "technical"
            )

        if self._has_numeric_score(
            smc
        ):
            core_setup_components.append(
                "smc"
            )

        direction = self._normalize_direction(
            fusion.get(
                "direction",
                "NEUTRAL",
            )
        )

        confluence = self._to_float(
            fusion.get(
                "confluence"
            )
        )

        if confluence is None:
            confluence = 0.0

        if len(core_setup_components) < self.MIN_CORE_COMPONENTS:

            return {
                "passed": False,
                "reason": "INSUFFICIENT_CORE_EVIDENCE",
                "core_components": core_setup_components,
                "available_components": core_components,
            }

        if direction not in {
            "BULLISH",
            "BEARISH",
        }:

            return {
                "passed": False,
                "reason": "NO_VALID_PRIMARY_DIRECTION",
                "core_components": core_setup_components,
                "available_components": core_components,
            }

        if confluence < self.MIN_WATCH_CONFLUENCE:

            return {
                "passed": False,
                "reason": "INSUFFICIENT_CONFLUENCE",
                "confluence": confluence,
                "required": self.MIN_WATCH_CONFLUENCE,
                "core_components": core_setup_components,
                "available_components": core_components,
            }

        return {
            "passed": True,
            "reason": "MINIMUM_EVIDENCE_CONFIRMED",
            "core_components": core_setup_components,
            "available_components": core_components,
            "confluence": confluence,
        }

    # ==========================================================
    # Optional Setup Validator
    # ==========================================================

    def _run_setup_validator(
        self,
        symbol: str,
        analysis_context: Dict[str, Any],
        fusion_result: Dict[str, Any],
    ) -> Dict[str, Any]:

        if self.setup_validator is None:

            return {
                "status": "NOT_CONFIGURED",
                "decision": "PASS",
            }

        context = dict(
            analysis_context
        )

        context["fusion"] = fusion_result
        context["fusion_result"] = fusion_result
        context["symbol"] = symbol

        # 🔥 Pass breakout retest info if available
        if "breakout_retest" in analysis_context:
            context["breakout_retest"] = analysis_context["breakout_retest"]

        result = self._call_engine(
            engine=self.setup_validator,
            preferred_methods=[
                "validate",
                "evaluate",
                "analyze",
            ],
            context=context,
            stage_name="SetupValidator",
        )

        if not result:

            return {
                "status": "UNAVAILABLE",
                "decision": "UNKNOWN",
            }

        return result

    # ==========================================================
    # 🔥 NEW: Breakout Memory Management
    # ==========================================================

    def _update_breakout_memory(
        self,
        symbol: str,
        smc_result: Dict[str, Any],
        df: Any,
    ) -> None:
        """
        Store breakout levels when SMC detects BOS/CHoCH with displacement.
        """
        if not smc_result:
            return

        last_structure = smc_result.get("last_structure")
        if last_structure not in {"BULLISH", "BEARISH"}:
            return

        # Check if there is a recent BOS/CHoCH event with displacement
        recent_events = smc_result.get("recent", {}).get("events", [])
        has_valid_breakout = False
        level = None

        for event in recent_events:
            if event.get("type") in {"BOS", "CHoCH"} and event.get("direction") == last_structure:
                # Check if this event has displacement (strength)
                # We'll use a simple threshold: if there's any displacement event nearby
                displacement_events = [
                    e for e in recent_events
                    if e.get("type") == "DISPLACEMENT" and e.get("direction") == last_structure
                ]
                if displacement_events:
                    has_valid_breakout = True
                    # Use the swing level from the event or current price
                    level = event.get("level")
                    break

        if not has_valid_breakout or level is None:
            # If no explicit level, use current close as reference
            try:
                level = float(df.iloc[-1]["close"])
            except:
                return

        # Store in memory
        self.breakout_memory[symbol] = {
            "level": level,
            "time": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
            "direction": last_structure,
            "level_type": "swing_high" if last_structure == "BULLISH" else "swing_low"
        }
        logger.info(
            "📌 Breakout stored for %s | direction=%s | level=%.6f",
            symbol,
            last_structure,
            level
        )

    def _check_breakout_retest(
        self,
        symbol: str,
        current_price: float,
        tolerance_pct: float = 2.0,
    ) -> Optional[Dict[str, Any]]:
        """
        Check if current price is retesting a stored breakout level.
        Returns the memory entry if retesting, else None.
        """
        if symbol not in self.breakout_memory:
            return None

        memory = self.breakout_memory[symbol]
        breakout_level = memory.get("level")
        if breakout_level is None or breakout_level <= 0:
            return None

        # Check if price is within tolerance of the breakout level
        diff_pct = abs(current_price - breakout_level) / breakout_level * 100
        if diff_pct <= tolerance_pct:
            logger.info(
                "🔄 Retest detected for %s | breakout=%.6f | current=%.6f | diff=%.2f%%",
                symbol,
                breakout_level,
                current_price,
                diff_pct
            )
            return memory

        return None

    # ==========================================================
    # Scan One Symbol
    # ==========================================================

    def scan_symbol(
        self,
        symbol: str,
    ) -> Dict[str, Any]:

        symbol = str(
            symbol
        ).strip().upper()

        logger.info(
            "🔍 Scanning %s",
            symbol,
        )

        # ======================================================
        # 1. Fetch OHLCV
        # ======================================================

        timeframe_data = (
            self._fetch_all_timeframes(
                symbol
            )
        )

        # ------------------------------------------------------
        # 15m is the primary technical/SMC setup timeframe.
        # ------------------------------------------------------

        df = timeframe_data.get(
            "15m"
        )

        if df is None:

            return {
                "status": "SKIPPED",
                "symbol": symbol,
                "reason": "NO_15M_OHLCV_DATA",
            }

        if len(df) < 50:

            return {
                "status": "SKIPPED",
                "symbol": symbol,
                "reason": "INSUFFICIENT_15M_CANDLES",
                "candles": len(df),
            }

        # ======================================================
        # Shared Context
        # ======================================================

        analysis_context = {
            "symbol": symbol,
            "df": df,
            "dataframe": df,
            "ohlcv": df,
            "timeframe_data": timeframe_data,
        }

        # ======================================================
        # 2. Technical
        # ======================================================

        technical_result = {}

        if self.technical_engine:

            try:

                technical_result = (
                    self._safe_dict(
                        self.technical_engine.analyze(
                            df
                        )
                    )
                )

                logger.info(
                    "Technical analysis complete | %s | "
                    "direction=%s | score=%s",
                    symbol,
                    technical_result.get(
                        "direction"
                    ),
                    technical_result.get(
                        "score"
                    ),
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

        # ======================================================
        # 3. SMC
        # ======================================================

        smc_result = {}

        if self.smc_engine:

            try:

                smc_result = (
                    self._safe_dict(
                        self.smc_engine.analyze(
                            df
                        )
                    )
                )

                logger.info(
                    "SMC analysis complete | %s | "
                    "direction=%s",
                    symbol,
                    smc_result.get(
                        "preferred_direction",
                        smc_result.get(
                            "direction"
                        ),
                    ),
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

        # ======================================================
        # 3.5 Score SMC via SetupValidator (if available)
        #
        # ✅ FIXED: SMC-এর নিজস্ব দিক ধরে রাখা হয়েছে এবং
        #           ইন্ডেন্টেশন ঠিক করা হয়েছে।
        # ======================================================

        smc_scored = smc_result  # fallback to raw

        if self.setup_validator is not None and self._has_real_analysis(smc_result):

            try:

                # Build context for the validator
                validator_context = {
                    "symbol": symbol,
                    "smc": smc_result,
                    "technical": technical_result,
                    "df": df,
                    "timeframe_data": timeframe_data,
                    "analysis_context": analysis_context,
                }

                # 🔥 Add breakout retest info to validator context
                current_price = float(df.iloc[-1]["close"])
                breakout_retest = self._check_breakout_retest(symbol, current_price)
                if breakout_retest:
                    validator_context["breakout_retest"] = breakout_retest
                    analysis_context["breakout_retest"] = breakout_retest

                validator_output = self._call_engine(
                    engine=self.setup_validator,
                    preferred_methods=[
                        "evaluate",
                        "validate",
                        "analyze",
                    ],
                    context=validator_context,
                    stage_name="SMC_Validator",
                )

                if validator_output and isinstance(validator_output, dict):

                    # Try preferred_direction, direction, then fallback to last_structure
                    original_smc_direction = self._normalize_direction(
                        smc_result.get("preferred_direction") or
                        smc_result.get("direction") or
                        smc_result.get("last_structure", "NEUTRAL")
                    )

                    # যে দিকেই SMC আছে, সেই দিকের স্কোর নিই
                    if original_smc_direction == "BULLISH":
                        scored_data = validator_output.get("bullish", {})
                    elif original_smc_direction == "BEARISH":
                        scored_data = validator_output.get("bearish", {})
                    else:
                        scored_data = {}

                    # Build a scored SMC dictionary
                    smc_scored = {
                        "score": scored_data.get("score", 0.0),
                        "direction": original_smc_direction,  # <-- আসল SMC দিক
                        "raw_validator": validator_output,
                        "raw_smc": smc_result,
                        "confidence": scored_data.get("confidence"),
                        "status": "SCORED",
                    }

                    logger.info(
                        "SMC scored via validator | %s | "
                        "direction=%s | score=%s",
                        symbol,
                        original_smc_direction,
                        smc_scored.get("score"),
                    )

                else:

                    smc_scored = smc_result
                    logger.warning(
                        "SMC validator returned no usable output | %s",
                        symbol,
                    )

            except Exception as exc:

                logger.warning(
                    "SMC validator evaluation failed | %s: %s",
                    symbol,
                    exc,
                )
                smc_scored = smc_result

        else:

            if self.setup_validator is None:
                logger.info(
                    "SMC setup validator not configured | %s",
                    symbol,
                )
            else:
                logger.info(
                    "SMC result insufficient for scoring | %s",
                    symbol,
                )

        # Update analysis_context with the scored SMC for later use
        analysis_context["smc_scored"] = smc_scored

        # ======================================================
        # 🔥 NEW: Update Breakout Memory
        # ======================================================

        if self._has_real_analysis(smc_result):
            self._update_breakout_memory(symbol, smc_result, df)

        # ======================================================
        # 4. Multi-Timeframe
        #
        # Exact contract:
        #
        # mtf_engine.evaluate(timeframe_data)
        #
        # Missing timeframe remains unavailable.
        # ======================================================

        mtf_result = {}

        if self.mtf_engine:

            try:

                evaluate_method = getattr(
                    self.mtf_engine,
                    "evaluate",
                    None,
                )

                if callable(
                    evaluate_method
                ):

                    mtf_result = (
                        self._safe_dict(
                            evaluate_method(
                                timeframe_data
                            )
                        )
                    )

                else:

                    mtf_result = (
                        self._call_engine(
                            engine=self.mtf_engine,
                            preferred_methods=[
                                "analyze",
                                "evaluate",
                            ],
                            context=analysis_context,
                            stage_name="MTF",
                        )
                    )

                logger.info(
                    "MTF analysis complete | %s | "
                    "direction=%s | score=%s | "
                    "alignment=%s | status=%s",
                    symbol,
                    mtf_result.get(
                        "direction"
                    ),
                    mtf_result.get(
                        "score"
                    ),
                    mtf_result.get(
                        "alignment"
                    ),
                    mtf_result.get(
                        "status"
                    ),
                )

            except Exception as exc:

                logger.exception(
                    "MTF analysis failed | %s: %s",
                    symbol,
                    exc,
                )

        else:

            logger.warning(
                "⚠️ MTF engine not configured | %s",
                symbol,
            )

        analysis_context[
            "mtf"
        ] = mtf_result

        # ======================================================
        # 5. Derivatives
        # ======================================================

        derivatives_result = {}

        if self.derivatives_engine:

            derivatives_context = dict(
                analysis_context
            )

            derivatives_result = (
                self._call_engine(
                    engine=self.derivatives_engine,
                    preferred_methods=[
                        "analyze",
                        "evaluate",
                    ],
                    context=derivatives_context,
                    stage_name="Derivatives",
                )
            )

            if derivatives_result:

                logger.info(
                    "Derivatives analysis complete | %s | "
                    "direction=%s | score=%s",
                    symbol,
                    derivatives_result.get(
                        "direction"
                    ),
                    derivatives_result.get(
                        "score"
                    ),
                )

        else:

            logger.warning(
                "⚠️ Derivatives engine not configured | %s",
                symbol,
            )

        analysis_context[
            "derivatives"
        ] = derivatives_result

        # ======================================================
        # 6. Market Context
        # ======================================================

        market_result = {}

        if self.market_context_engine:

            market_context = dict(
                analysis_context
            )

            market_context[
                "symbol"
            ] = symbol

            market_result = (
                self._call_engine(
                    engine=self.market_context_engine,
                    preferred_methods=[
                        "analyze",
                        "evaluate",
                        "get_context",
                    ],
                    context=market_context,
                    stage_name="MarketContext",
                )
            )

        else:

            logger.warning(
                "⚠️ Market context engine not configured | %s",
                symbol,
            )

        analysis_context[
            "market"
        ] = market_result

        # ======================================================
        # Safety Gate
        # ======================================================

        technical_available = (
            self._has_real_analysis(
                technical_result
            )
        )

        smc_available = (
            self._has_real_analysis(
                smc_result
            )
        )

        mtf_available = (
            self._has_real_analysis(
                mtf_result
            )
        )

        derivatives_available = (
            self._has_real_analysis(
                derivatives_result
            )
        )

        if (
            not technical_available
            and not smc_available
        ):

            return {
                "status": "SKIPPED",
                "symbol": symbol,
                "reason": "NO_CORE_ANALYSIS_DATA",
                "technical": technical_result,
                "smc": smc_result,
                "mtf": mtf_result,
                "derivatives": derivatives_result,
                "market": market_result,
            }

        # ======================================================
        # 7. Signal Fusion
        # ======================================================

        if self.fusion_engine is None:

            return {
                "status": "SKIPPED",
                "symbol": symbol,
                "reason": "NO_FUSION_ENGINE",
                "technical": technical_result,
                "smc": smc_result,
                "mtf": mtf_result,
                "derivatives": derivatives_result,
                "market": market_result,
            }

        try:

            fusion_result = (
                self._safe_dict(
                    self.fusion_engine.evaluate(
                        technical=technical_result,
                        smc=smc_scored,                     # <-- SMC SCORED
                        mtf=mtf_result,
                        derivatives=derivatives_result,
                        market=market_result,
                        ai=None,
                    )
                )
            )

        except TypeError:

            # Compatibility with fusion engines that do not
            # expose the optional AI argument.

            try:

                fusion_result = (
                    self._safe_dict(
                        self.fusion_engine.evaluate(
                            technical=technical_result,
                            smc=smc_scored,                 # <-- SMC SCORED
                            mtf=mtf_result,
                            derivatives=derivatives_result,
                            market=market_result,
                        )
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
                }

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
            }

        if not fusion_result:

            return {
                "status": "ERROR",
                "symbol": symbol,
                "reason": "EMPTY_FUSION_RESULT",
            }

        # ======================================================
        # Fusion Summary
        # ======================================================

        score = self._to_float(
            fusion_result.get(
                "score"
            )
        )

        direction = self._normalize_direction(
            fusion_result.get(
                "direction",
                "NEUTRAL",
            )
        )

        grade = str(
            fusion_result.get(
                "grade",
                "D",
            )
        ).upper()

        state = str(
            fusion_result.get(
                "state",
                "NO_CLEAR_SETUP",
            )
        ).upper()

        confluence = self._to_float(
            fusion_result.get(
                "confluence"
            )
        )

        if confluence is None:
            confluence = 0.0

        logger.info(
            "Fusion result | %s | "
            "direction=%s | score=%s | "
            "grade=%s | state=%s | "
            "confluence=%.2f",
            symbol,
            direction,
            score,
            grade,
            state,
            confluence,
        )

        # ======================================================
        # 8. Minimum Evidence Gate
        # ======================================================

        evidence_result = (
            self._minimum_evidence_gate(
                technical=technical_result,
                smc=smc_scored,                     # <-- SMC SCORED
                mtf=mtf_result,
                derivatives=derivatives_result,
                fusion=fusion_result,
            )
        )

        if not evidence_result.get(
            "passed",
            False,
        ):

            return {
                "status": "REJECTED",
                "symbol": symbol,
                "score": score,
                "direction": direction,
                "grade": grade,
                "state": state,
                "confluence": confluence,
                "technical": technical_result,
                "smc": smc_scored,                  # <-- SMC SCORED (consistency)
                "mtf": mtf_result,
                "derivatives": derivatives_result,
                "market": market_result,
                "fusion": fusion_result,
                "evidence": evidence_result,
                "reason": evidence_result.get(
                    "reason",
                    "MINIMUM_EVIDENCE_GATE",
                ),
            }

        # ======================================================
        # 9. Optional Setup Validator
        # ======================================================

        validator_result = (
            self._run_setup_validator(
                symbol=symbol,
                analysis_context=analysis_context,
                fusion_result=fusion_result,
            )
        )

        validator_decision = str(
            validator_result.get(
                "decision",
                validator_result.get(
                    "verdict",
                    "PASS",
                ),
            )
        ).upper()

        if validator_decision in {
            "REJECT",
            "REJECTED",
            "NO_TRADE",
            "BLOCK",
            "BLOCKED",
        }:

            return {
                "status": "REJECTED",
                "symbol": symbol,
                "score": score,
                "direction": direction,
                "grade": grade,
                "state": state,
                "confluence": confluence,
                "technical": technical_result,
                "smc": smc_scored,                  # <-- SMC SCORED
                "mtf": mtf_result,
                "derivatives": derivatives_result,
                "market": market_result,
                "fusion": fusion_result,
                "evidence": evidence_result,
                "validator": validator_result,
                "reason": "SETUP_VALIDATOR",
            }

        # ======================================================
        # 10. Quality Gate
        # ======================================================

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

        if (
            score is None
            or score < minimum_score
        ):

            return {
                "status": "REJECTED",
                "symbol": symbol,
                "score": score,
                "direction": direction,
                "grade": grade,
                "state": state,
                "confluence": confluence,
                "technical": technical_result,
                "smc": smc_scored,                  # <-- SMC SCORED
                "mtf": mtf_result,
                "derivatives": derivatives_result,
                "market": market_result,
                "fusion": fusion_result,
                "evidence": evidence_result,
                "validator": validator_result,
                "reason": "QUALITY_GATE",
            }

        # ======================================================
        # 11. Direction Gate
        # ======================================================

        if direction not in {
            "BULLISH",
            "BEARISH",
        }:

            return {
                "status": "REJECTED",
                "symbol": symbol,
                "score": score,
                "direction": direction,
                "grade": grade,
                "state": state,
                "confluence": confluence,
                "fusion": fusion_result,
                "reason": "INVALID_DIRECTION",
            }

        # ======================================================
        # 12. State Gate (✅ FIXED: WEAK_SETUP যোগ করা হলো)
        #
        # IMPORTANT:
        #
        # TRADE_CANDIDATE:
        #     score >= 70
        #     confluence >= 70
        #
        # WATCH:
        #     score >= 70
        #     confluence >= 60
        #
        # WEAK_SETUP:
        #     score >= 60 (SCAN_MIN_SCORE=60 সেট করলে পাস করবে)
        # ======================================================

        if state not in {
            "TRADE_CANDIDATE",
            "WATCH",
            "WEAK_SETUP",  # <-- এই লাইন যোগ করা হয়েছে
        }:

            return {
                "status": "REJECTED",
                "symbol": symbol,
                "score": score,
                "direction": direction,
                "grade": grade,
                "state": state,
                "confluence": confluence,
                "technical": technical_result,
                "smc": smc_scored,                  # <-- SMC SCORED
                "mtf": mtf_result,
                "derivatives": derivatives_result,
                "market": market_result,
                "fusion": fusion_result,
                "evidence": evidence_result,
                "reason": "SETUP_STATE_GATE",
            }

        # ------------------------------------------------------
        # Additional state/confluence consistency check.
        # ------------------------------------------------------

        if (
            state == "TRADE_CANDIDATE"
            and confluence < self.MIN_TRADE_CONFLUENCE
        ):

            return {
                "status": "REJECTED",
                "symbol": symbol,
                "score": score,
                "direction": direction,
                "grade": grade,
                "state": state,
                "confluence": confluence,
                "fusion": fusion_result,
                "reason": "TRADE_CONFLUENCE_GATE",
            }

        if (
            state == "WATCH"
            and confluence < self.MIN_WATCH_CONFLUENCE
        ):

            return {
                "status": "REJECTED",
                "symbol": symbol,
                "score": score,
                "direction": direction,
                "grade": grade,
                "state": state,
                "confluence": confluence,
                "fusion": fusion_result,
                "reason": "WATCH_CONFLUENCE_GATE",
            }

        # ======================================================
        # 13. Gemini Review
        #
        # Gemini is optional.
        #
        # It reviews an existing setup.
        # It does NOT create one.
        # ======================================================

        gemini_result = {}

        if self.gemini_reviewer:

            try:

                review_payload = {
                    "symbol": symbol,
                    "technical": technical_result,
                    "smc": smc_scored,                  # <-- SMC SCORED
                    "mtf": mtf_result,
                    "derivatives": derivatives_result,
                    "market": market_result,
                    "fusion": fusion_result,
                    "evidence": evidence_result,
                }

                review_method = getattr(
                    self.gemini_reviewer,
                    "review",
                    None,
                )

                if callable(
                    review_method
                ):

                    gemini_result = (
                        self._safe_dict(
                            review_method(
                                review_payload
                            )
                        )
                    )

                else:

                    gemini_result = (
                        self._call_engine(
                            engine=self.gemini_reviewer,
                            preferred_methods=[
                                "analyze",
                                "evaluate",
                            ],
                            context=review_payload,
                            stage_name="Gemini",
                        )
                    )

                logger.info(
                    "🤖 Gemini review complete | %s | "
                    "decision=%s",
                    symbol,
                    gemini_result.get(
                        "decision",
                        gemini_result.get(
                            "verdict"
                        ),
                    ),
                )

            except Exception as exc:

                logger.warning(
                    "Gemini review failed | %s: %s",
                    symbol,
                    exc,
                )

                # Gemini failure does NOT create fake approval
                # and does NOT automatically reject the setup.
                gemini_result = {
                    "status": "ERROR",
                    "decision": "UNAVAILABLE",
                    "error": str(exc),
                }

        else:

            gemini_result = {
                "status": "NOT_CONFIGURED",
                "decision": "UNAVAILABLE",
            }

        # ======================================================
        # 14. Gemini Gate
        # ======================================================

        gemini_decision = str(
            gemini_result.get(
                "decision",
                gemini_result.get(
                    "verdict",
                    "UNKNOWN",
                ),
            )
        ).upper().strip()

        if gemini_decision in {
            "REJECT",
            "REJECTED",
            "NO_TRADE",
            "BLOCK",
            "BLOCKED",
        }:

            return {
                "status": "REJECTED",
                "symbol": symbol,
                "score": score,
                "direction": direction,
                "grade": grade,
                "state": state,
                "confluence": confluence,
                "technical": technical_result,
                "smc": smc_scored,                  # <-- SMC SCORED
                "mtf": mtf_result,
                "derivatives": derivatives_result,
                "market": market_result,
                "fusion": fusion_result,
                "evidence": evidence_result,
                "validator": validator_result,
                "gemini": gemini_result,
                "reason": "GEMINI_REJECTION",
            }

        # ======================================================
        # 15. Trade Plan
        # ======================================================

        trade_plan = {}

        if self.trade_plan_engine:

            try:

                build_method = getattr(
                    self.trade_plan_engine,
                    "build",
                    None,
                )

                if callable(
                    build_method
                ):

                    trade_plan = (
                        self._safe_dict(
                            build_method(
                                symbol=symbol,
                                dataframe=df,
                                fusion_result=fusion_result,
                                gemini_result=gemini_result,
                            )
                        )
                    )

                else:

                    trade_plan = (
                        self._call_engine(
                            engine=self.trade_plan_engine,
                            preferred_methods=[
                                "create",
                                "build",
                                "generate",
                                "evaluate",
                            ],
                            context={
                                "symbol": symbol,
                                "df": df,
                                "fusion": fusion_result,
                                "gemini": gemini_result,
                                "technical": technical_result,
                                "smc": smc_scored,          # <-- SMC SCORED
                                "mtf": mtf_result,
                                "derivatives": derivatives_result,
                                "market": market_result,
                            },
                            stage_name="TradePlan",
                        )
                    )

                logger.info(
                    "Trade plan complete | %s",
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

        else:

            trade_plan = {
                "status": "NOT_CONFIGURED",
            }

        # ======================================================
        # 16. Risk Engine
        # ======================================================

        risk_result = {}

        if self.risk_engine:

            try:

                evaluate_method = getattr(
                    self.risk_engine,
                    "evaluate",
                    None,
                )

                if callable(
                    evaluate_method
                ):

                    try:

                        risk_result = (
                            self._safe_dict(
                                evaluate_method(
                                    symbol=symbol,
                                    fusion_result=fusion_result,
                                    gemini_result=gemini_result,
                                    trade_plan=trade_plan,
                                )
                            )
                        )

                    except TypeError:

                        risk_result = (
                            self._call_engine(
                                engine=self.risk_engine,
                                preferred_methods=[
                                    "evaluate",
                                    "build_trade_execution_plan",
                                    "assess",
                                ],
                                context={
                                    "symbol": symbol,
                                    "fusion": fusion_result,
                                    "fusion_result": fusion_result,
                                    "gemini": gemini_result,
                                    "gemini_result": gemini_result,
                                    "trade_plan": trade_plan,
                                    "technical": technical_result,
                                    "smc": smc_scored,          # <-- SMC SCORED
                                    "mtf": mtf_result,
                                    "derivatives": derivatives_result,
                                    "market": market_result,
                                },
                                stage_name="Risk",
                            )
                        )

                else:

                    risk_result = (
                        self._call_engine(
                            engine=self.risk_engine,
                            preferred_methods=[
                                "assess",
                                "evaluate",
                                "build_trade_execution_plan",
                            ],
                            context={
                                "symbol": symbol,
                                "fusion": fusion_result,
                                "trade_plan": trade_plan,
                                "gemini": gemini_result,
                                "technical": technical_result,
                                "smc": smc_scored,          # <-- SMC SCORED
                                "mtf": mtf_result,
                                "derivatives": derivatives_result,
                                "market": market_result,
                            },
                            stage_name="Risk",
                        )
                    )

                logger.info(
                    "Risk evaluation complete | %s | "
                    "decision=%s | status=%s",
                    symbol,
                    risk_result.get(
                        "decision"
                    ),
                    risk_result.get(
                        "status"
                    ),
                )

            except Exception as exc:

                logger.warning(
                    "Risk evaluation failed | %s: %s",
                    symbol,
                    exc,
                )

                risk_result = {
                    "status": "ERROR",
                    "decision": "UNAVAILABLE",
                    "error": str(exc),
                }

        else:

            risk_result = {
                "status": "NOT_CONFIGURED",
                "decision": "UNAVAILABLE",
            }

        # ======================================================
        # 17. Risk Gate
        #
        # If Risk Engine exists and explicitly rejects,
        # it has veto authority.
        #
        # If Risk Engine is unavailable, Scanner does not
        # manufacture an approval.
        # ======================================================

        risk_decision = str(
            risk_result.get(
                "decision",
                risk_result.get(
                    "verdict",
                    "",
                ),
            )
        ).upper().strip()

        risk_status = str(
            risk_result.get(
                "status",
                "",
            )
        ).upper().strip()

        if risk_decision in {
            "REJECT",
            "REJECTED",
            "NO_TRADE",
            "BLOCK",
            "BLOCKED",
            "INVALID",
        }:

            return {
                "status": "REJECTED",
                "symbol": symbol,
                "score": score,
                "direction": direction,
                "grade": grade,
                "state": state,
                "confluence": confluence,
                "technical": technical_result,
                "smc": smc_scored,                  # <-- SMC SCORED
                "mtf": mtf_result,
                "derivatives": derivatives_result,
                "market": market_result,
                "fusion": fusion_result,
                "evidence": evidence_result,
                "validator": validator_result,
                "gemini": gemini_result,
                "trade_plan": trade_plan,
                "risk": risk_result,
                "reason": "RISK_ENGINE",
            }

        if risk_status in {
            "ERROR",
            "FAILED",
        }:

            # Do not claim a risk-approved trade when the risk
            # engine failed.
            return {
                "status": "REJECTED",
                "symbol": symbol,
                "score": score,
                "direction": direction,
                "grade": grade,
                "state": state,
                "confluence": confluence,
                "technical": technical_result,
                "smc": smc_scored,                  # <-- SMC SCORED
                "mtf": mtf_result,
                "derivatives": derivatives_result,
                "market": market_result,
                "fusion": fusion_result,
                "evidence": evidence_result,
                "validator": validator_result,
                "gemini": gemini_result,
                "trade_plan": trade_plan,
                "risk": risk_result,
                "reason": "RISK_ENGINE_UNAVAILABLE",
            }

        # ======================================================
        # 18. Final Candidate
        # ======================================================

        logger.info(
            "🎯 CANDIDATE | %s | "
            "score=%s | direction=%s | "
            "state=%s | confluence=%.2f",
            symbol,
            score,
            direction,
            state,
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
            "smc": smc_scored,                  # <-- SMC SCORED
            "mtf": mtf_result,
            "derivatives": derivatives_result,
            "market": market_result,

            "fusion": fusion_result,
            "evidence": evidence_result,
            "validator": validator_result,

            "gemini": gemini_result,
            "trade_plan": trade_plan,
            "risk": risk_result,

            "status_detail": {
                "technical_available": technical_available,
                "smc_available": smc_available,
                "mtf_available": mtf_available,
                "derivatives_available": derivatives_available,
                "gemini_available": bool(
                    self.gemini_reviewer
                ),
                "risk_available": bool(
                    self.risk_engine
                ),
            },
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

        if limit < 1:
            limit = 1

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

        if not universe:

            logger.warning(
                "Coin universe is empty"
            )

            return []

        logger.info(
            "🌎 Universe size: %s",
            len(universe),
        )

        selected_coins = universe[
            :limit
        ]

        logger.info(
            "🔎 Scanning %s coins",
            len(selected_coins),
        )

        results = []

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

        # ======================================================
        # Summary
        # ======================================================

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
