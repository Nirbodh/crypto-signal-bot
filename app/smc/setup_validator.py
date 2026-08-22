import logging
from typing import Any, Dict, List, Optional


logger = logging.getLogger("crypto-signal-bot")


class SMCSetupValidator:
    """
    SMC setup quality validator.

    IMPORTANT:
    This is NOT a final trading signal engine.

    It evaluates confluence:
        Liquidity Sweep
        + CHoCH / BOS
        + Displacement
        + FVG
        + Order Block
        + Premium / Discount
        + Price location

    ✅ FIXED:
        - recent_window now actually used.
        - Mitigated FVG/OB no longer score.
        - Structural gate added (Sweep OR BOS/CHoCH required).
        - ✅ NEW: Zone Re-entry (Active FVG/OB + Discount/Premium).
        - ✅ NEW: Rejection candle check for pullback confirmation.
        - ✅ NEW: Breakout Retest (stored breakout level + retest + rejection candle).
        - Setup validity flag added.
    """

    def __init__(
        self,
        recent_window: int = 20,
    ):
        self.recent_window = recent_window

    # ==========================================================
    # Helpers
    # ==========================================================

    @staticmethod
    def _empty_setup(
        direction: str,
    ) -> Dict[str, Any]:

        return {
            "direction": direction,
            "score": 0,
            "grade": "NO_SETUP",
            "evidence": [],
            "warnings": [],
            "zones": [],
            "setup_valid": False,
        }

    @staticmethod
    def _is_recent(
        event_index: int,
        latest_index: int,
        window: int,
    ) -> bool:
        """Check if event is within recent window."""
        return (latest_index - event_index) <= window

    @staticmethod
    def _is_bullish_rejection_candle(
        data,
    ) -> bool:
        """
        Check if the latest candle is a bullish rejection (pinbar/hammer).
        Lower wick > body, close > open, and low < previous low but close > previous close.
        """
        if data is None or len(data) < 2:
            return False

        try:
            last = data.iloc[-1]
            prev = data.iloc[-2]

            open_price = float(last["open"])
            close_price = float(last["close"])
            high = float(last["high"])
            low = float(last["low"])
            prev_low = float(prev["low"])
            prev_close = float(prev["close"])

            body = abs(close_price - open_price)
            lower_wick = min(open_price, close_price) - low
            upper_wick = high - max(open_price, close_price)

            # Bullish candle with lower wick > body (pinbar/hammer)
            if close_price > open_price and lower_wick > body * 1.5:
                # Also check if it made a lower low but closed higher than previous close
                if low < prev_low and close_price > prev_close:
                    return True
        except:
            pass

        return False

    @staticmethod
    def _is_bearish_rejection_candle(
        data,
    ) -> bool:
        """
        Check if the latest candle is a bearish rejection (shooting star/pinbar).
        Upper wick > body, close < open, and high > previous high but close < previous close.
        """
        if data is None or len(data) < 2:
            return False

        try:
            last = data.iloc[-1]
            prev = data.iloc[-2]

            open_price = float(last["open"])
            close_price = float(last["close"])
            high = float(last["high"])
            low = float(last["low"])
            prev_high = float(prev["high"])
            prev_close = float(prev["close"])

            body = abs(close_price - open_price)
            lower_wick = min(open_price, close_price) - low
            upper_wick = high - max(open_price, close_price)

            # Bearish candle with upper wick > body (shooting star)
            if close_price < open_price and upper_wick > body * 1.5:
                # Also check if it made a higher high but closed lower than previous close
                if high > prev_high and close_price < prev_close:
                    return True
        except:
            pass

        return False

    # ==========================================================
    # Bullish setup
    # ==========================================================

    def evaluate_bullish(
        self,
        smc_result: Dict[str, Any],
        **kwargs,  # Accept additional context
    ) -> Dict[str, Any]:

        result = self._empty_setup(
            "BULLISH"
        )

        evidence: List[str] = []
        warnings: List[str] = []
        zones: List[Dict[str, Any]] = []

        score = 0

        recent = smc_result.get(
            "recent",
            {},
        )

        premium_discount = smc_result.get(
            "premium_discount",
            {},
        )

        # Get latest index for recency check
        latest_index = smc_result.get("current_index", 0)
        data = smc_result.get("data")
        if not latest_index and data is not None and hasattr(data, 'index'):
            latest_index = data.index[-1] if len(data) > 0 else 0

        # 🔥 Extract breakout retest info from kwargs if provided
        breakout_retest = kwargs.get("breakout_retest")
        has_breakout_retest = False
        if breakout_retest and isinstance(breakout_retest, dict):
            # Check if the retest direction matches the target direction
            if breakout_retest.get("direction") == "BULLISH":
                has_breakout_retest = True

        # ==========================================================
        # 🔥 STRUCTURAL GATE + ZONE RE-ENTRY + BREAKOUT RETEST
        # ==========================================================

        has_bullish_sweep = False
        has_bullish_structure = False

        for event in recent.get(
            "events",
            [],
        ):
            # Skip if not recent
            if not self._is_recent(event.get("index", 0), latest_index, self.recent_window):
                continue

            if (
                event.get("type")
                == "LIQUIDITY_SWEEP"
                and event.get("direction")
                == "BULLISH"
            ):
                has_bullish_sweep = True

            if (
                event.get("type")
                in {"CHoCH", "BOS"}
                and event.get("direction")
                == "BULLISH"
            ):
                has_bullish_structure = True

        # Check for active FVG/OB (not mitigated)
        bullish_fvgs = [
            gap
            for gap in recent.get("fvg", [])
            if gap.get("direction") == "BULLISH"
            and self._is_recent(gap.get("index", 0), latest_index, self.recent_window)
            and gap.get("mitigated", False) is False
        ]
        has_active_bullish_fvg = len(bullish_fvgs) > 0

        bullish_obs = [
            block
            for block in recent.get("order_blocks", [])
            if block.get("direction") == "BULLISH"
            and self._is_recent(block.get("index", 0), latest_index, self.recent_window)
            and block.get("mitigated", False) is False
        ]
        has_active_bullish_ob = len(bullish_obs) > 0

        zone_state = premium_discount.get("state")
        in_discount = (zone_state == "DISCOUNT")

        # Check rejection candle
        bullish_rejection = self._is_bullish_rejection_candle(data)

        # Gate condition:
        # Option 1: Fresh structural evidence (sweep or BOS/CHoCH)
        structural_ok = has_bullish_sweep or has_bullish_structure

        # Option 2: Zone Re-entry (Active FVG/OB + Discount) + Rejection Candle
        zone_reentry_ok = (
            (has_active_bullish_fvg or has_active_bullish_ob)
            and in_discount
            and bullish_rejection
        )

        # Option 3: Breakout Retest (stored breakout level + retest + rejection candle)
        breakout_retest_ok = (
            has_breakout_retest
            and bullish_rejection
        )

        if not (structural_ok or zone_reentry_ok or breakout_retest_ok):
            result["warnings"].append(
                "No recent structural evidence (sweep/BOS/CHoCH) or valid pullback/retest setup"
            )
            result["setup_valid"] = False
            return result

        result["setup_valid"] = True

        # If zone re-entry detected, add evidence
        if zone_reentry_ok:
            evidence.append("Bullish pullback / zone re-entry detected")
            if has_active_bullish_fvg:
                evidence.append("Active FVG in discount zone")
            if has_active_bullish_ob:
                evidence.append("Active Order Block in discount zone")
            if bullish_rejection:
                evidence.append("Bullish rejection candle confirmed")

        if breakout_retest_ok:
            evidence.append("Bullish breakout retest detected")
            if bullish_rejection:
                evidence.append("Bullish rejection candle confirmed")

        # ------------------------------------------------------
        # 1. Bullish liquidity sweep
        # ------------------------------------------------------

        bullish_sweep = False

        for event in recent.get(
            "events",
            [],
        ):
            if not self._is_recent(event.get("index", 0), latest_index, self.recent_window):
                continue

            if (
                event.get("type")
                == "LIQUIDITY_SWEEP"
                and event.get("direction")
                == "BULLISH"
            ):
                bullish_sweep = True
                break

        if bullish_sweep:

            score += 25

            evidence.append(
                "Bullish liquidity sweep detected"
            )

        else:

            warnings.append(
                "No recent bullish liquidity sweep"
            )

        # ------------------------------------------------------
        # 2. Bullish CHoCH / BOS
        # ------------------------------------------------------

        bullish_structure = False

        for event in recent.get(
            "events",
            [],
        ):
            if not self._is_recent(event.get("index", 0), latest_index, self.recent_window):
                continue

            if (
                event.get("type")
                in {"CHoCH", "BOS"}
                and event.get("direction")
                == "BULLISH"
            ):

                bullish_structure = True
                break

        if bullish_structure:

            score += 20

            evidence.append(
                "Bullish structure confirmation"
            )

        else:

            warnings.append(
                "No recent bullish BOS/CHoCH"
            )

        # ------------------------------------------------------
        # 3. Bullish displacement
        # ------------------------------------------------------

        bullish_displacement = False

        for event in recent.get(
            "events",
            [],
        ):
            if not self._is_recent(event.get("index", 0), latest_index, self.recent_window):
                continue

            if (
                event.get("type")
                == "DISPLACEMENT"
                and event.get("direction")
                == "BULLISH"
            ):

                bullish_displacement = True
                break

        if bullish_displacement:

            score += 15

            evidence.append(
                "Bullish displacement detected"
            )

        else:

            warnings.append(
                "No recent bullish displacement"
            )

        # ------------------------------------------------------
        # 4. Bullish FVG (only if not mitigated)
        # ------------------------------------------------------

        if bullish_fvgs:

            score += 15

            evidence.append(
                "Active bullish FVG available"
            )

            for gap in bullish_fvgs[-3:]:

                zones.append({
                    "type": "FVG",
                    "direction": "BULLISH",
                    "lower": gap["lower"],
                    "upper": gap["upper"],
                    "midpoint": gap["midpoint"],
                    "mitigated": gap.get(
                        "mitigated",
                        False,
                    ),
                })

        else:

            warnings.append(
                "No recent active bullish FVG"
            )

        # ------------------------------------------------------
        # 5. Bullish Order Block (only if not mitigated)
        # ------------------------------------------------------

        if bullish_obs:

            score += 15

            evidence.append(
                "Active bullish order block available"
            )

            for block in bullish_obs[-3:]:

                zones.append({
                    "type": "ORDER_BLOCK",
                    "direction": "BULLISH",
                    "lower": block["lower"],
                    "upper": block["upper"],
                    "mitigated": block.get(
                        "mitigated",
                        False,
                    ),
                })

        else:

            warnings.append(
                "No recent active bullish order block"
            )

        # ------------------------------------------------------
        # 6. Discount zone
        # ------------------------------------------------------

        if in_discount:

            score += 10

            evidence.append(
                "Price is in discount zone"
            )

        elif zone_state == "PREMIUM":

            warnings.append(
                "Price is currently in premium zone"
            )

        else:

            warnings.append(
                "Premium/discount state unclear"
            )

        # ------------------------------------------------------
        # Grade
        # ------------------------------------------------------

        result["score"] = min(
            score,
            100,
        )

        result["evidence"] = evidence

        result["warnings"] = warnings

        result["zones"] = zones

        if score >= 80:

            result["grade"] = "A"

        elif score >= 65:

            result["grade"] = "B"

        elif score >= 45:

            result["grade"] = "C"

        elif score > 0:

            result["grade"] = "D"

        else:

            result["grade"] = "NO_SETUP"

        # If setup is invalid, score is 0 regardless
        if not result["setup_valid"]:
            result["score"] = 0
            result["grade"] = "NO_SETUP"

        return result

    # ==========================================================
    # Bearish setup
    # ==========================================================

    def evaluate_bearish(
        self,
        smc_result: Dict[str, Any],
        **kwargs,
    ) -> Dict[str, Any]:

        result = self._empty_setup(
            "BEARISH"
        )

        evidence: List[str] = []
        warnings: List[str] = []
        zones: List[Dict[str, Any]] = []

        score = 0

        recent = smc_result.get(
            "recent",
            {},
        )

        premium_discount = smc_result.get(
            "premium_discount",
            {},
        )

        # Get latest index for recency check
        latest_index = smc_result.get("current_index", 0)
        data = smc_result.get("data")
        if not latest_index and data is not None and hasattr(data, 'index'):
            latest_index = data.index[-1] if len(data) > 0 else 0

        # 🔥 Extract breakout retest info from kwargs
        breakout_retest = kwargs.get("breakout_retest")
        has_breakout_retest = False
        if breakout_retest and isinstance(breakout_retest, dict):
            if breakout_retest.get("direction") == "BEARISH":
                has_breakout_retest = True

        # ==========================================================
        # 🔥 STRUCTURAL GATE + ZONE RE-ENTRY + BREAKOUT RETEST (Bearish)
        # ==========================================================

        has_bearish_sweep = False
        has_bearish_structure = False

        for event in recent.get(
            "events",
            [],
        ):
            if not self._is_recent(event.get("index", 0), latest_index, self.recent_window):
                continue

            if (
                event.get("type")
                == "LIQUIDITY_SWEEP"
                and event.get("direction")
                == "BEARISH"
            ):
                has_bearish_sweep = True

            if (
                event.get("type")
                in {"CHoCH", "BOS"}
                and event.get("direction")
                == "BEARISH"
            ):
                has_bearish_structure = True

        # Check for active FVG/OB (not mitigated)
        bearish_fvgs = [
            gap
            for gap in recent.get("fvg", [])
            if gap.get("direction") == "BEARISH"
            and self._is_recent(gap.get("index", 0), latest_index, self.recent_window)
            and gap.get("mitigated", False) is False
        ]
        has_active_bearish_fvg = len(bearish_fvgs) > 0

        bearish_obs = [
            block
            for block in recent.get("order_blocks", [])
            if block.get("direction") == "BEARISH"
            and self._is_recent(block.get("index", 0), latest_index, self.recent_window)
            and block.get("mitigated", False) is False
        ]
        has_active_bearish_ob = len(bearish_obs) > 0

        zone_state = premium_discount.get("state")
        in_premium = (zone_state == "PREMIUM")

        # Check rejection candle
        bearish_rejection = self._is_bearish_rejection_candle(data)

        # Gate condition:
        # Option 1: Fresh structural evidence
        structural_ok = has_bearish_sweep or has_bearish_structure

        # Option 2: Zone Re-entry (Active FVG/OB + Premium) + Rejection Candle
        zone_reentry_ok = (
            (has_active_bearish_fvg or has_active_bearish_ob)
            and in_premium
            and bearish_rejection
        )

        # Option 3: Breakout Retest
        breakout_retest_ok = (
            has_breakout_retest
            and bearish_rejection
        )

        if not (structural_ok or zone_reentry_ok or breakout_retest_ok):
            result["warnings"].append(
                "No recent structural evidence (sweep/BOS/CHoCH) or valid pullback/retest setup"
            )
            result["setup_valid"] = False
            return result

        result["setup_valid"] = True

        if zone_reentry_ok:
            evidence.append("Bearish pullback / zone re-entry detected")
            if has_active_bearish_fvg:
                evidence.append("Active FVG in premium zone")
            if has_active_bearish_ob:
                evidence.append("Active Order Block in premium zone")
            if bearish_rejection:
                evidence.append("Bearish rejection candle confirmed")

        if breakout_retest_ok:
            evidence.append("Bearish breakout retest detected")
            if bearish_rejection:
                evidence.append("Bearish rejection candle confirmed")

        # ------------------------------------------------------
        # 1. Bearish liquidity sweep
        # ------------------------------------------------------

        bearish_sweep = False

        for event in recent.get(
            "events",
            [],
        ):
            if not self._is_recent(event.get("index", 0), latest_index, self.recent_window):
                continue

            if (
                event.get("type")
                == "LIQUIDITY_SWEEP"
                and event.get("direction")
                == "BEARISH"
            ):

                bearish_sweep = True
                break

        if bearish_sweep:

            score += 25

            evidence.append(
                "Bearish liquidity sweep detected"
            )

        else:

            warnings.append(
                "No recent bearish liquidity sweep"
            )

        # ------------------------------------------------------
        # 2. Bearish CHoCH / BOS
        # ------------------------------------------------------

        bearish_structure = False

        for event in recent.get(
            "events",
            [],
        ):
            if not self._is_recent(event.get("index", 0), latest_index, self.recent_window):
                continue

            if (
                event.get("type")
                in {"CHoCH", "BOS"}
                and event.get("direction")
                == "BEARISH"
            ):

                bearish_structure = True
                break

        if bearish_structure:

            score += 20

            evidence.append(
                "Bearish structure confirmation"
            )

        else:

            warnings.append(
                "No recent bearish BOS/CHoCH"
            )

        # ------------------------------------------------------
        # 3. Bearish displacement
        # ------------------------------------------------------

        bearish_displacement = False

        for event in recent.get(
            "events",
            [],
        ):
            if not self._is_recent(event.get("index", 0), latest_index, self.recent_window):
                continue

            if (
                event.get("type")
                == "DISPLACEMENT"
                and event.get("direction")
                == "BEARISH"
            ):

                bearish_displacement = True
                break

        if bearish_displacement:

            score += 15

            evidence.append(
                "Bearish displacement detected"
            )

        else:

            warnings.append(
                "No recent bearish displacement"
            )

        # ------------------------------------------------------
        # 4. Bearish FVG (only if not mitigated)
        # ------------------------------------------------------

        if bearish_fvgs:

            score += 15

            evidence.append(
                "Active bearish FVG available"
            )

            for gap in bearish_fvgs[-3:]:

                zones.append({
                    "type": "FVG",
                    "direction": "BEARISH",
                    "lower": gap["lower"],
                    "upper": gap["upper"],
                    "midpoint": gap["midpoint"],
                    "mitigated": gap.get(
                        "mitigated",
                        False,
                    ),
                })

        else:

            warnings.append(
                "No recent active bearish FVG"
            )

        # ------------------------------------------------------
        # 5. Bearish Order Block (only if not mitigated)
        # ------------------------------------------------------

        if bearish_obs:

            score += 15

            evidence.append(
                "Active bearish order block available"
            )

            for block in bearish_obs[-3:]:

                zones.append({
                    "type": "ORDER_BLOCK",
                    "direction": "BEARISH",
                    "lower": block["lower"],
                    "upper": block["upper"],
                    "mitigated": block.get(
                        "mitigated",
                        False,
                    ),
                })

        else:

            warnings.append(
                "No recent active bearish order block"
            )

        # ------------------------------------------------------
        # 6. Premium zone
        # ------------------------------------------------------

        if in_premium:

            score += 10

            evidence.append(
                "Price is in premium zone"
            )

        elif zone_state == "DISCOUNT":

            warnings.append(
                "Price is currently in discount zone"
            )

        else:

            warnings.append(
                "Premium/discount state unclear"
            )

        # ------------------------------------------------------
        # Grade
        # ------------------------------------------------------

        result["score"] = min(
            score,
            100,
        )

        result["evidence"] = evidence

        result["warnings"] = warnings

        result["zones"] = zones

        if score >= 80:

            result["grade"] = "A"

        elif score >= 65:

            result["grade"] = "B"

        elif score >= 45:

            result["grade"] = "C"

        elif score > 0:

            result["grade"] = "D"

        else:

            result["grade"] = "NO_SETUP"

        # If setup is invalid, score is 0 regardless
        if not result["setup_valid"]:
            result["score"] = 0
            result["grade"] = "NO_SETUP"

        return result

    # ==========================================================
    # Main
    # ==========================================================

    def evaluate(
        self,
        smc_result: Optional[
            Dict[str, Any]
        ],
        **kwargs,  # Accept additional context like breakout_retest
    ) -> Dict[str, Any]:

        if not smc_result:

            return {
                "bullish": self._empty_setup(
                    "BULLISH"
                ),
                "bearish": self._empty_setup(
                    "BEARISH"
                ),
                "preferred_direction": (
                    "NEUTRAL"
                ),
                "setup_valid": False,
            }

        # Pass kwargs to individual evaluators
        bullish = self.evaluate_bullish(
            smc_result,
            **kwargs
        )

        bearish = self.evaluate_bearish(
            smc_result,
            **kwargs
        )

        # ------------------------------------------------------
        # Preferred direction (only if setup is valid)
        # ------------------------------------------------------

        if bullish["setup_valid"] and bearish["setup_valid"]:

            if (
                bullish["score"]
                > bearish["score"]
            ):
                preferred = "BULLISH"
            elif (
                bearish["score"]
                > bullish["score"]
            ):
                preferred = "BEARISH"
            else:
                preferred = "NEUTRAL"

        elif bullish["setup_valid"]:
            preferred = "BULLISH"
        elif bearish["setup_valid"]:
            preferred = "BEARISH"
        else:
            preferred = "NEUTRAL"

        # Overall setup validity
        setup_valid = (
            bullish["setup_valid"] or bearish["setup_valid"]
        )

        return {
            "bullish": bullish,
            "bearish": bearish,
            "preferred_direction": preferred,
            "setup_valid": setup_valid,
        }
