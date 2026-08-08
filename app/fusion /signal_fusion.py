import logging
from typing import Any, Dict, Optional

logger = logging.getLogger("crypto-signal-bot")


class SignalFusionEngine:
    """
    Combines:

        Technical
        SMC
        MTF
        Derivatives
        Market/Fundamental

    into one flexible setup score.

    IMPORTANT:
    This is NOT a guaranteed prediction engine.

    It measures confluence and setup quality.
    """

    def __init__(
        self,
        weights: Optional[
            Dict[str, float]
        ] = None,
    ):

        self.weights = weights or {
            "technical": 0.25,
            "smc": 0.25,
            "mtf": 0.20,
            "derivatives": 0.15,
            "market": 0.10,
            "ai": 0.05,
        }

    # ==========================================================
    # Helpers
    # ==========================================================

    @staticmethod
    def _safe_score(
        data: Any,
        default: float = 50.0,
    ) -> float:

        if not isinstance(
            data,
            dict,
        ):

            return default

        value = data.get(
            "score"
        )

        try:

            value = float(value)

        except (
            TypeError,
            ValueError,
        ):

            return default

        return max(
            0.0,
            min(
                100.0,
                value,
            ),
        )

    # ==========================================================
    # Direction extraction
    # ==========================================================

    @staticmethod
    def _direction(
        data: Any,
    ) -> str:

        if not isinstance(
            data,
            dict,
        ):

            return "NEUTRAL"

        direction = data.get(
            "direction"
        )

        if direction in {
            "BULLISH",
            "BEARISH",
        }:

            return direction

        return "NEUTRAL"

    # ==========================================================
    # SMC score
    # ==========================================================

    def _get_smc_score(
        self,
        smc: Dict[str, Any],
        direction: str,
    ) -> float:

        if direction == "BULLISH":

            bullish = smc.get(
                "bullish",
                {},
            )

            return self._safe_score(
                bullish
            )

        if direction == "BEARISH":

            bearish = smc.get(
                "bearish",
                {},
            )

            return self._safe_score(
                bearish
            )

        return 50.0

    # ==========================================================
    # Market score
    # ==========================================================

    def _get_market_score(
        self,
        market: Dict[str, Any],
        direction: str,
    ) -> float:

        fundamental = market.get(
            "fundamental",
            {},
        )

        score = 50.0

        # ------------------------------------------------------
        # 24h momentum
        # ------------------------------------------------------

        change = fundamental.get(
            "change_24h"
        )

        try:

            change = float(change)

        except (
            TypeError,
            ValueError,
        ):

            change = 0.0

        if direction == "BULLISH":

            if change > 0:

                score += min(
                    20,
                    change * 2,
                )

            elif change < 0:

                score -= min(
                    20,
                    abs(change) * 2,
                )

        elif direction == "BEARISH":

            if change < 0:

                score += min(
                    20,
                    abs(change) * 2,
                )

            elif change > 0:

                score -= min(
                    20,
                    change * 2,
                )

        return max(
            0,
            min(
                100,
                score,
            ),
        )

    # ==========================================================
    # Directional component score
    # ==========================================================

    def _directional_score(
        self,
        score: float,
        component_direction: str,
        target_direction: str,
    ) -> float:

        if (
            component_direction
            == target_direction
        ):

            return score

        if (
            component_direction
            == "NEUTRAL"
        ):

            # Neutral should not destroy
            # an otherwise good setup.

            return 50.0

        # Opposite direction reduces confidence,
        # but does not automatically reject.

        return max(
            0.0,
            100.0 - score,
        )

    # ==========================================================
    # Main fusion
    # ==========================================================

    def evaluate(
        self,
        technical: Optional[
            Dict[str, Any]
        ] = None,

        smc: Optional[
            Dict[str, Any]
        ] = None,

        mtf: Optional[
            Dict[str, Any]
        ] = None,

        derivatives: Optional[
            Dict[str, Any]
        ] = None,

        market: Optional[
            Dict[str, Any]
        ] = None,

        ai: Optional[
            Dict[str, Any]
        ] = None,
    ) -> Dict[str, Any]:

        technical = (
            technical or {}
        )

        smc = (
            smc or {}
        )

        mtf = (
            mtf or {}
        )

        derivatives = (
            derivatives or {}
        )

        market = (
            market or {}
        )

        ai = (
            ai or {}
        )

        # ------------------------------------------------------
        # Determine primary direction
        # ------------------------------------------------------

        directions = []

        for source in (
            technical,
            mtf,
            derivatives,
        ):

            direction = self._direction(
                source
            )

            if direction != "NEUTRAL":

                directions.append(
                    direction
                )

        bullish_count = directions.count(
            "BULLISH"
        )

        bearish_count = directions.count(
            "BEARISH"
        )

        if bullish_count > bearish_count:

            direction = "BULLISH"

        elif bearish_count > bullish_count:

            direction = "BEARISH"

        else:

            smc_direction = smc.get(
                "preferred_direction",
                "NEUTRAL",
            )

            if smc_direction in {
                "BULLISH",
                "BEARISH",
            }:

                direction = smc_direction

            else:

                direction = "NEUTRAL"

        # ------------------------------------------------------
        # Component scores
        # ------------------------------------------------------

        technical_score = (
            self._safe_score(
                technical
            )
        )

        mtf_score = (
            self._safe_score(
                mtf
            )
        )

        derivatives_score = (
            self._safe_score(
                derivatives
            )
        )

        smc_score = (
            self._get_smc_score(
                smc,
                direction,
            )
        )

        market_score = (
            self._get_market_score(
                market,
                direction,
            )
        )

        ai_score = (
            self._safe_score(
                ai
            )
            if ai
            else 50.0
        )

        # ------------------------------------------------------
        # Directional adjustment
        # ------------------------------------------------------

        technical_score = (
            self._directional_score(
                technical_score,
                self._direction(
                    technical
                ),
                direction,
            )
        )

        mtf_score = (
            self._directional_score(
                mtf_score,
                self._direction(
                    mtf
                ),
                direction,
            )
        )

        derivatives_score = (
            self._directional_score(
                derivatives_score,
                self._direction(
                    derivatives
                ),
                direction,
            )
        )

        # ------------------------------------------------------
        # Weighted score
        # ------------------------------------------------------

        weighted_score = (
            technical_score
            * self.weights["technical"]
        )

        weighted_score += (
            smc_score
            * self.weights["smc"]
        )

        weighted_score += (
            mtf_score
            * self.weights["mtf"]
        )

        weighted_score += (
            derivatives_score
            * self.weights["derivatives"]
        )

        weighted_score += (
            market_score
            * self.weights["market"]
        )

        weighted_score += (
            ai_score
            * self.weights["ai"]
        )

        weighted_score = max(
            0.0,
            min(
                100.0,
                weighted_score,
            ),
        )

        # ------------------------------------------------------
        # Grade
        # ------------------------------------------------------

        if weighted_score >= 90:

            grade = "A+"

        elif weighted_score >= 80:

            grade = "A"

        elif weighted_score >= 70:

            grade = "B"

        elif weighted_score >= 60:

            grade = "C"

        else:

            grade = "D"

        # ------------------------------------------------------
        # Signal state
        # ------------------------------------------------------

        if weighted_score >= 80:

            state = "TRADE_CANDIDATE"

        elif weighted_score >= 70:

            state = "WATCH"

        elif weighted_score >= 60:

            state = "WEAK_SETUP"

        else:

            state = "NO_CLEAR_SETUP"

        # ------------------------------------------------------
        # Confluence
        # ------------------------------------------------------

        component_directions = {
            "technical": self._direction(
                technical
            ),
            "smc": (
                smc.get(
                    "preferred_direction",
                    "NEUTRAL",
                )
            ),
            "mtf": self._direction(
                mtf
            ),
            "derivatives": self._direction(
                derivatives
            ),
        }

        aligned = 0
        active = 0

        for name, component_direction in (
            component_directions.items()
        ):

            if component_direction == "NEUTRAL":
                continue

            active += 1

            if (
                component_direction
                == direction
            ):

                aligned += 1

        if active > 0:

            confluence = (
                aligned
                / active
            ) * 100

        else:

            confluence = 0

        # ------------------------------------------------------
        # Warnings
        # ------------------------------------------------------

        warnings = []

        if (
            confluence < 50
            and direction != "NEUTRAL"
        ):

            warnings.append(
                "Directional disagreement "
                "between analysis modules"
            )

        funding = (
            derivatives
            .get("funding", {})
        )

        if funding.get(
            "risk"
        ) == "HIGH":

            warnings.append(
                "Extreme funding / crowded positioning"
            )

        entry_timing = mtf.get(
            "entry_timing"
        )

        if entry_timing == "CONTRARY":

            warnings.append(
                "Lower timeframe is "
                "currently against primary direction"
            )

        # ------------------------------------------------------
        # Final result
        # ------------------------------------------------------

        return {
            "direction": direction,

            "score": round(
                weighted_score,
                2,
            ),

            "grade": grade,

            "state": state,

            "confluence": round(
                confluence,
                2,
            ),

            "components": {
                "technical": round(
                    technical_score,
                    2,
                ),
                "smc": round(
                    smc_score,
                    2,
                ),
                "mtf": round(
                    mtf_score,
                    2,
                ),
                "derivatives": round(
                    derivatives_score,
                    2,
                ),
                "market": round(
                    market_score,
                    2,
                ),
                "ai": round(
                    ai_score,
                    2,
                ),
            },

            "warnings": warnings,

            "status": "SUCCESS",
        }
