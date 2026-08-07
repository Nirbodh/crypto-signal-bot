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

    No single condition is a mandatory hard filter.
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
        }

    # ==========================================================
    # Bullish setup
    # ==========================================================

    def evaluate_bullish(
        self,
        smc_result: Dict[str, Any],
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

        # ------------------------------------------------------
        # 1. Bullish liquidity sweep
        # ------------------------------------------------------

        bullish_sweep = False

        for event in recent.get(
            "events",
            [],
        ):

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
        # 4. Bullish FVG
        # ------------------------------------------------------

        bullish_fvgs = [
            gap
            for gap in recent.get(
                "fvg",
                [],
            )
            if gap.get("direction")
            == "BULLISH"
        ]

        if bullish_fvgs:

            score += 15

            evidence.append(
                "Bullish FVG available"
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
                "No recent bullish FVG"
            )

        # ------------------------------------------------------
        # 5. Bullish Order Block
        # ------------------------------------------------------

        bullish_obs = [
            block
            for block in recent.get(
                "order_blocks",
                [],
            )
            if block.get("direction")
            == "BULLISH"
        ]

        if bullish_obs:

            score += 15

            evidence.append(
                "Bullish order block available"
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
                "No recent bullish order block"
            )

        # ------------------------------------------------------
        # 6. Discount zone
        # ------------------------------------------------------

        zone_state = premium_discount.get(
            "state"
        )

        if zone_state == "DISCOUNT":

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

        return result

    # ==========================================================
    # Bearish setup
    # ==========================================================

    def evaluate_bearish(
        self,
        smc_result: Dict[str, Any],
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

        # ------------------------------------------------------
        # 1. Bearish liquidity sweep
        # ------------------------------------------------------

        bearish_sweep = False

        for event in recent.get(
            "events",
            [],
        ):

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
        # 4. Bearish FVG
        # ------------------------------------------------------

        bearish_fvgs = [
            gap
            for gap in recent.get(
                "fvg",
                [],
            )
            if gap.get("direction")
            == "BEARISH"
        ]

        if bearish_fvgs:

            score += 15

            evidence.append(
                "Bearish FVG available"
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
                "No recent bearish FVG"
            )

        # ------------------------------------------------------
        # 5. Bearish Order Block
        # ------------------------------------------------------

        bearish_obs = [
            block
            for block in recent.get(
                "order_blocks",
                [],
            )
            if block.get("direction")
            == "BEARISH"
        ]

        if bearish_obs:

            score += 15

            evidence.append(
                "Bearish order block available"
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
                "No recent bearish order block"
            )

        # ------------------------------------------------------
        # 6. Premium zone
        # ------------------------------------------------------

        zone_state = premium_discount.get(
            "state"
        )

        if zone_state == "PREMIUM":

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

        return result

    # ==========================================================
    # Main
    # ==========================================================

    def evaluate(
        self,
        smc_result: Optional[
            Dict[str, Any]
        ],
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
            }

        bullish = self.evaluate_bullish(
            smc_result
        )

        bearish = self.evaluate_bearish(
            smc_result
        )

        # ------------------------------------------------------
        # Preferred direction
        # ------------------------------------------------------

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

        return {
            "bullish": bullish,
            "bearish": bearish,
            "preferred_direction": preferred,
        }
