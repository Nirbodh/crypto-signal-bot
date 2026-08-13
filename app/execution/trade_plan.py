import logging
from typing import Any, Dict, Optional


logger = logging.getLogger("crypto-signal-bot")


class TradePlanEngine:
    """
    Builds a trader-friendly execution plan.

    Supports:

        LONG
        SHORT

    Priority:

        1. Structure / SMC invalidation
        2. ATR-based fallback

    TP levels are calculated from risk distance.
    """

    def __init__(
        self,
        minimum_rr: float = 1.5,
        default_tp1_rr: float = 1.0,
        default_tp2_rr: float = 2.0,
        default_tp3_rr: float = 3.0,
        atr_multiplier: float = 1.5,
    ):

        self.minimum_rr = minimum_rr

        self.default_tp1_rr = (
            default_tp1_rr
        )

        self.default_tp2_rr = (
            default_tp2_rr
        )

        self.default_tp3_rr = (
            default_tp3_rr
        )

        self.atr_multiplier = (
            atr_multiplier
        )

    # ==========================================================
    # Helpers
    # ==========================================================

    @staticmethod
    def _number(
        value: Any,
    ) -> Optional[float]:

        if value is None:
            return None

        try:

            return float(value)

        except (
            TypeError,
            ValueError,
        ):

            return None

    # ==========================================================
    # LONG SL
    # ==========================================================

    def _long_stop(
        self,
        entry: float,
        structure_low: Optional[float],
        atr: Optional[float],
    ) -> Optional[float]:

        # Prefer structure invalidation.

        if (
            structure_low is not None
            and structure_low < entry
        ):

            return structure_low

        # ATR fallback.

        if (
            atr is not None
            and atr > 0
        ):

            return (
                entry
                - (
                    atr
                    * self.atr_multiplier
                )
            )

        return None

    # ==========================================================
    # SHORT SL
    # ==========================================================

    def _short_stop(
        self,
        entry: float,
        structure_high: Optional[float],
        atr: Optional[float],
    ) -> Optional[float]:

        if (
            structure_high is not None
            and structure_high > entry
        ):

            return structure_high

        if (
            atr is not None
            and atr > 0
        ):

            return (
                entry
                + (
                    atr
                    * self.atr_multiplier
                )
            )

        return None

    # ==========================================================
    # LONG TP
    # ==========================================================

    @staticmethod
    def _long_targets(
        entry: float,
        risk: float,
        rr1: float,
        rr2: float,
        rr3: float,
    ) -> Dict[str, float]:

        return {
            "tp1": entry + (
                risk * rr1
            ),

            "tp2": entry + (
                risk * rr2
            ),

            "tp3": entry + (
                risk * rr3
            ),
        }

    # ==========================================================
    # SHORT TP
    # ==========================================================

    @staticmethod
    def _short_targets(
        entry: float,
        risk: float,
        rr1: float,
        rr2: float,
        rr3: float,
    ) -> Dict[str, float]:

        return {
            "tp1": entry - (
                risk * rr1
            ),

            "tp2": entry - (
                risk * rr2
            ),

            "tp3": entry - (
                risk * rr3
            ),
        }

    # ==========================================================
    # Main build_plan
    # ==========================================================

    def build_plan(
        self,
        direction: str,
        entry: Any,
        atr: Any = None,
        structure_low: Any = None,
        structure_high: Any = None,
        tp1_rr: Optional[float] = None,
        tp2_rr: Optional[float] = None,
        tp3_rr: Optional[float] = None,
    ) -> Dict[str, Any]:

        direction = (
            str(direction)
            .upper()
        )

        entry_price = self._number(
            entry
        )

        atr_value = self._number(
            atr
        )

        low = self._number(
            structure_low
        )

        high = self._number(
            structure_high
        )

        if (
            direction
            not in {
                "LONG",
                "SHORT",
                "BULLISH",
                "BEARISH",
            }
        ):

            return {
                "status": "INVALID",
                "reason": (
                    "Unsupported direction"
                ),
            }

        if entry_price is None or entry_price <= 0:

            return {
                "status": "INVALID",
                "reason": (
                    "Invalid entry price"
                ),
            }

        if direction == "BULLISH":

            direction = "LONG"

        elif direction == "BEARISH":

            direction = "SHORT"

        rr1 = (
            tp1_rr
            if tp1_rr is not None
            else self.default_tp1_rr
        )

        rr2 = (
            tp2_rr
            if tp2_rr is not None
            else self.default_tp2_rr
        )

        rr3 = (
            tp3_rr
            if tp3_rr is not None
            else self.default_tp3_rr
        )

        # ------------------------------------------------------
        # Stop loss
        # ------------------------------------------------------

        if direction == "LONG":

            stop_loss = self._long_stop(
                entry_price,
                low,
                atr_value,
            )

        else:

            stop_loss = self._short_stop(
                entry_price,
                high,
                atr_value,
            )

        if (
            stop_loss is None
            or stop_loss <= 0
        ):

            return {
                "status": "INVALID",
                "reason": (
                    "Unable to calculate stop loss"
                ),
            }

        # ------------------------------------------------------
        # Risk distance
        # ------------------------------------------------------

        risk_distance = abs(
            entry_price
            - stop_loss
        )

        if risk_distance <= 0:

            return {
                "status": "INVALID",
                "reason": (
                    "Risk distance is zero"
                ),
            }

        risk_percent = (
            risk_distance
            / entry_price
        ) * 100

        # ------------------------------------------------------
        # Targets
        # ------------------------------------------------------

        if direction == "LONG":

            targets = (
                self._long_targets(
                    entry_price,
                    risk_distance,
                    rr1,
                    rr2,
                    rr3,
                )
            )

        else:

            targets = (
                self._short_targets(
                    entry_price,
                    risk_distance,
                    rr1,
                    rr2,
                    rr3,
                )
            )

        # ------------------------------------------------------
        # Validation
        # ------------------------------------------------------

        warnings = []

        if rr1 < self.minimum_rr:

            warnings.append(
                "TP1 is below minimum R:R preference"
            )

        # Very wide stop warning.

        if risk_percent > 8:

            warnings.append(
                "Stop distance is unusually wide"
            )

        return {
            "status": "SUCCESS",

            "direction": direction,

            "entry": round(
                entry_price,
                12,
            ),

            "stop_loss": round(
                stop_loss,
                12,
            ),

            "risk_distance": round(
                risk_distance,
                12,
            ),

            "risk_percent": round(
                risk_percent,
                4,
            ),

            "tp1": round(
                targets["tp1"],
                12,
            ),

            "tp2": round(
                targets["tp2"],
                12,
            ),

            "tp3": round(
                targets["tp3"],
                12,
            ),

            "rr": {
                "tp1": rr1,
                "tp2": rr2,
                "tp3": rr3,
            },

            "warnings": warnings,
        }

    # ==========================================================
    # ✅ FIXED Build method for scanner compatibility
    # ==========================================================

    def build(
        self,
        symbol: Optional[str] = None,
        dataframe: Any = None,
        fusion_result: Optional[Dict[str, Any]] = None,
        gemini_result: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:

        """
        Build trade plan from fusion result.

        This method is called by ScannerEngine.
        """

        if not fusion_result:
            return {
                "status": "INVALID",
                "reason": "No fusion result provided",
            }

        direction = fusion_result.get("direction", "NEUTRAL")
        score = fusion_result.get("score", 0)

        # ==========================================================
        # 🔥 1. Entry Price বের করা
        # ==========================================================

        entry_price = 0

        # A. Dataframe থেকে নেওয়ার চেষ্টা
        if dataframe is not None and hasattr(dataframe, 'iloc') and len(dataframe) > 0:
            try:
                entry_price = float(dataframe.iloc[-1]["close"])
                logger.info(f"📊 Entry from dataframe close: {entry_price} for {symbol}")
            except (KeyError, IndexError, TypeError, ValueError) as e:
                logger.warning(f"⚠️ Could not get close from dataframe for {symbol}: {e}")

        # B. Dataframe এ না পেলে, ফিউশন রেজাল্ট থেকে নেওয়া
        if entry_price <= 0 and fusion_result:
            # চেষ্টা করি 'price' ফিল্ড থেকে
            entry_price = fusion_result.get("price", 0)
            if entry_price <= 0:
                # অথবা 'entry' ফিল্ড থেকে
                entry_price = fusion_result.get("entry", 0)
            if entry_price > 0:
                logger.info(f"📊 Entry from fusion_result: {entry_price} for {symbol}")

        # C. একদম শেষ চেষ্টা - ডিফল্ট ফ্যালব্যাক (কখনো হওয়া উচিত না)
        if entry_price <= 0:
            logger.warning(f"⚠️ No price found for {symbol}, using fallback price 1.0")
            entry_price = 1.0

        # ==========================================================
        # 🔥 2. ATR বের করা
        # ==========================================================

        atr_value = None

        if dataframe is not None and hasattr(dataframe, 'iloc') and len(dataframe) > 0:
            try:
                if "atr" in dataframe.columns:
                    atr_value = float(dataframe.iloc[-1]["atr"])
                    logger.info(f"📊 ATR from dataframe: {atr_value} for {symbol}")
            except (KeyError, IndexError, TypeError, ValueError) as e:
                logger.warning(f"⚠️ Could not get ATR from dataframe for {symbol}: {e}")

        # ATR না পেলে, ২% ডিফল্ট সেট করা
        if atr_value is None or atr_value <= 0:
            atr_value = entry_price * 0.02
            logger.info(f"📊 Using default ATR (2%): {atr_value} for {symbol}")

        # ==========================================================
        # 🔥 3. সাপোর্ট / রেসিস্ট্যান্স বের করা
        # ==========================================================

        support = fusion_result.get("support")
        resistance = fusion_result.get("resistance")

        # ==========================================================
        # 🔥 4. Build Plan কল করা
        # ==========================================================

        plan = self.build_plan(
            direction=direction,
            entry=entry_price,
            atr=atr_value,
            structure_low=support,
            structure_high=resistance,
        )

        # ==========================================================
        # 🔥 5. Plan INVALID হলে ফ্যালব্যাক প্ল্যান তৈরি করা
        # ==========================================================

        if plan.get("status") != "SUCCESS":
            logger.warning(f"⚠️ Trade plan failed for {symbol}, creating fallback plan")

            # ডিফল্ট স্টপ লস (এন্ট্রি থেকে ২%)
            if direction in ("BULLISH", "LONG"):
                stop_loss = entry_price * 0.98
            else:
                stop_loss = entry_price * 1.02

            risk_distance = abs(entry_price - stop_loss)

            plan = {
                "status": "SUCCESS",
                "direction": direction,
                "entry": round(entry_price, 12),
                "stop_loss": round(stop_loss, 12),
                "risk_distance": round(risk_distance, 12),
                "risk_percent": round((risk_distance / entry_price) * 100, 4),
                "tp1": round(entry_price + risk_distance * 1.0, 12),
                "tp2": round(entry_price + risk_distance * 2.0, 12),
                "tp3": round(entry_price + risk_distance * 3.0, 12),
                "warnings": ["Fallback trade plan used - no valid entry/stop found"]
            }

        return plan
