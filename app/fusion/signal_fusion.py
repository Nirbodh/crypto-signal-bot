import logging
from typing import Any, Dict, Optional


logger = logging.getLogger("crypto-signal-bot")


class SignalFusionEngine:
    """
    Production-oriented Signal Fusion Engine.

    Combines:

        - Technical Analysis
        - Smart Money Concepts (SMC)
        - Multi-Timeframe Analysis (MTF)
        - Derivatives
        - Market / Fundamental Data
        - AI Review

    The engine measures setup quality and confluence.

    IMPORTANT:
        This is NOT a prediction engine.
        A high score does not guarantee a profitable trade.

    Design principles:
        1. Missing data must not artificially increase confidence.
        2. Directional disagreement must reduce confidence.
        3. AI acts primarily as a reviewer/validator.
        4. Trade candidates require both score and confluence.
        5. Component weights are normalized dynamically.
    """

    # ==========================================================
    # Initialization
    # ==========================================================

    def __init__(
        self,
        weights: Optional[Dict[str, float]] = None,
    ) -> None:

        self.weights = weights or {
            "technical": 0.25,
            "smc": 0.25,
            "mtf": 0.20,
            "derivatives": 0.15,
            "market": 0.10,
            "ai": 0.05,
        }

        self._validate_weights()

    # ==========================================================
    # Weight Validation
    # ==========================================================

    def _validate_weights(self) -> None:
        """
        Validate fusion weights.

        We intentionally allow the total to be different from 1.0
        because weights are normalized dynamically.
        """

        for name, weight in self.weights.items():

            if not isinstance(weight, (int, float)):

                raise TypeError(
                    f"Weight for '{name}' must be numeric."
                )

            if weight < 0:

                raise ValueError(
                    f"Weight for '{name}' cannot be negative."
                )

    # ==========================================================
    # Safe Score
    # ==========================================================

    @staticmethod
    def _safe_score(
        data: Any,
        default: Optional[float] = None,
    ) -> Optional[float]:
        """
        Extract score safely.

        Returns None when score is unavailable instead of
        automatically assigning 50.

        This prevents missing modules from creating fake confidence.
        """

        if not isinstance(data, dict):

            return default

        value = data.get("score")

        try:

            value = float(value)

        except (TypeError, ValueError):

            return default

        return max(
            0.0,
            min(
                100.0,
                value,
            ),
        )

    # ==========================================================
    # Direction
    # ==========================================================

    @staticmethod
    def _direction(
        data: Any,
    ) -> str:
        """
        Extract normalized direction.
        """

        if not isinstance(data, dict):

            return "NEUTRAL"

        direction = str(
            data.get(
                "direction",
                "NEUTRAL",
            )
        ).upper()

        if direction in {
            "BULLISH",
            "BEARISH",
        }:

            return direction

        return "NEUTRAL"

    # ==========================================================
    # SMC Score
    # ==========================================================

    def _get_smc_score(
        self,
        smc: Dict[str, Any],
        direction: str,
    ) -> Optional[float]:
        """
        Extract direction-specific SMC score.
        """

        if not smc:

            return None

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

        # Some SMC engines may expose a direct score.

        return self._safe_score(
            smc
        )

    # ==========================================================
    # Market Score
    # ==========================================================

    def _get_market_score(
        self,
        market: Dict[str, Any],
        direction: str,
    ) -> Optional[float]:
        """
        Calculate market/fundamental directional score.

        Uses 24h momentum when available.
        """

        if not market:

            return None

        fundamental = market.get(
            "fundamental",
            {},
        )

        if not isinstance(
            fundamental,
            dict,
        ):

            fundamental = {}

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

        score = 50.0

        if direction == "BULLISH":

            if change > 0:

                score += min(
                    20.0,
                    change * 2.0,
                )

            elif change < 0:

                score -= min(
                    20.0,
                    abs(change) * 2.0,
                )

        elif direction == "BEARISH":

            if change < 0:

                score += min(
                    20.0,
                    abs(change) * 2.0,
                )

            elif change > 0:

                score -= min(
                    20.0,
                    change * 2.0,
                )

        return max(
            0.0,
            min(
                100.0,
                score,
            ),
        )

    # ==========================================================
    # Directional Score
    # ==========================================================

    @staticmethod
    def _directional_score(
        score: Optional[float],
        component_direction: str,
        target_direction: str,
    ) -> Optional[float]:
        """
        Adjust score according to directional alignment.

        Same direction:
            Keep score.

        Neutral:
            Keep the score but apply a confidence reduction.

        Opposite direction:
            Penalize strongly.

        Returns None when score is unavailable.
        """

        if score is None:

            return None

        if target_direction == "NEUTRAL":

            return score

        if component_direction == target_direction:

            return score

        if component_direction == "NEUTRAL":

            # Neutral information should not become a
            # strong positive or negative signal.

            return score * 0.75

        # Opposite direction.

        return max(
            0.0,
            score * 0.35,
        )

    # ==========================================================
    # Weighted Fusion
    # ==========================================================

    def _calculate_weighted_score(
        self,
        component_scores: Dict[str, Optional[float]],
    ) -> float:
        """
        Calculate weighted score using only available components.

        Missing components do NOT receive artificial 50 scores.
        """

        weighted_total = 0.0
        active_weight = 0.0

        for component, score in component_scores.items():

            if score is None:

                continue

            weight = self.weights.get(
                component,
                0.0,
            )

            if weight <= 0:

                continue

            weighted_total += (
                score * weight
            )

            active_weight += weight

        if active_weight <= 0:

            return 0.0

        score = (
            weighted_total
            / active_weight
        )

        return max(
            0.0,
            min(
                100.0,
                score,
            ),
        )

    # ==========================================================
    # Primary Direction
    # ==========================================================

    def _determine_primary_direction(
        self,
        technical: Dict[str, Any],
        smc: Dict[str, Any],
        mtf: Dict[str, Any],
        derivatives: Dict[str, Any],
    ) -> str:
        """
        Determine primary market direction.

        Technical, MTF and derivatives vote first.
        SMC acts as secondary confirmation.
        """

        votes = []

        sources = (
            technical,
            mtf,
            derivatives,
        )

        for source in sources:

            direction = self._direction(
                source
            )

            if direction != "NEUTRAL":

                votes.append(
                    direction
                )

        bullish_votes = votes.count(
            "BULLISH"
        )

        bearish_votes = votes.count(
            "BEARISH"
        )

        if bullish_votes > bearish_votes:

            return "BULLISH"

        if bearish_votes > bullish_votes:

            return "BEARISH"

        # Tie-breaker: SMC

        smc_direction = str(
            smc.get(
                "preferred_direction",
                "NEUTRAL",
            )
        ).upper()

        if smc_direction in {
            "BULLISH",
            "BEARISH",
        }:

            return smc_direction

        return "NEUTRAL"

    # ==========================================================
    # Confluence
    # ==========================================================

    def _calculate_confluence(
        self,
        component_directions: Dict[str, str],
        target_direction: str,
    ) -> float:
        """
        Calculate directional confluence.

        Neutral components are ignored.
        """

        if target_direction == "NEUTRAL":

            return 0.0

        active = 0
        aligned = 0

        for component_direction in (
            component_directions.values()
        ):

            if component_direction == "NEUTRAL":

                continue

            active += 1

            if (
                component_direction
                == target_direction
            ):

                aligned += 1

        if active == 0:

            return 0.0

        return (
            aligned
            / active
        ) * 100.0

    # ==========================================================
    # Warnings
    # ==========================================================

    def _build_warnings(
        self,
        direction: str,
        confluence: float,
        derivatives: Dict[str, Any],
        mtf: Dict[str, Any],
        component_scores: Dict[str, Optional[float]],
    ) -> list:
        """
        Build risk and quality warnings.
        """

        warnings = []

        # ------------------------------------------------------
        # Directional disagreement
        # ------------------------------------------------------

        if (
            direction != "NEUTRAL"
            and confluence < 50
        ):

            warnings.append(
                "Directional disagreement "
                "between analysis modules"
            )

        # ------------------------------------------------------
        # Weak confluence
        # ------------------------------------------------------

        if (
            direction != "NEUTRAL"
            and confluence < 70
        ):

            warnings.append(
                "Confluence below preferred "
                "trade threshold"
            )

        # ------------------------------------------------------
        # Missing components
        # ------------------------------------------------------

        missing = [
            name
            for name, score
            in component_scores.items()
            if score is None
        ]

        if missing:

            warnings.append(
                "Missing analysis components: "
                + ", ".join(missing)
            )

        # ------------------------------------------------------
        # Funding
        # ------------------------------------------------------

        funding = derivatives.get(
            "funding",
            {},
        )

        if isinstance(
            funding,
            dict,
        ):

            if funding.get(
                "risk"
            ) == "HIGH":

                warnings.append(
                    "Extreme funding / "
                    "crowded positioning"
                )

        # ------------------------------------------------------
        # MTF entry timing
        # ------------------------------------------------------

        entry_timing = mtf.get(
            "entry_timing"
        )

        if entry_timing == "CONTRARY":

            warnings.append(
                "Lower timeframe is currently "
                "against primary direction"
            )

        # ------------------------------------------------------
        # Weak score
        # ------------------------------------------------------

        for name, score in component_scores.items():

            if (
                score is not None
                and score < 35
            ):

                warnings.append(
                    f"Weak {name} component"
                )

        return warnings

    # ==========================================================
    # Grade
    # ==========================================================

    @staticmethod
    def _get_grade(
        score: float,
    ) -> str:

        if score >= 90:

            return "A+"

        if score >= 80:

            return "A"

        if score >= 70:

            return "B"

        if score >= 60:

            return "C"

        return "D"

    # ==========================================================
    # Signal State
    # ==========================================================

    @staticmethod
    def _get_state(
        score: float,
        confluence: float,
        direction: str,
        warnings: list,
    ) -> str:
        """
        Determine final signal state.

        A trade candidate requires:

            Score >= 80
            Confluence >= 70%
            Valid direction
            No critical risk warning
        """

        if direction == "NEUTRAL":

            return "NO_CLEAR_SETUP"

        critical_warning = any(
            (
                "Extreme funding"
                in warning
                )
            for warning in warnings
        )

        if (
            score >= 80
            and confluence >= 70
            and not critical_warning
        ):

            return "TRADE_CANDIDATE"

        if (
            score >= 70
            and confluence >= 60
        ):

            return "WATCH"

        if score >= 60:

            return "WEAK_SETUP"

        return "NO_CLEAR_SETUP"

    # ==========================================================
    # Main Evaluation
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

        technical = technical or {}
        smc = smc or {}
        mtf = mtf or {}
        derivatives = derivatives or {}
        market = market or {}
        ai = ai or {}

        # ------------------------------------------------------
        # Primary direction
        # ------------------------------------------------------

        direction = (
            self._determine_primary_direction(
                technical,
                smc,
                mtf,
                derivatives,
            )
        )

        # ------------------------------------------------------
        # Raw component scores
        # ------------------------------------------------------

        raw_scores = {

            "technical": self._safe_score(
                technical
            ),

            "smc": self._get_smc_score(
                smc,
                direction,
            ),

            "mtf": self._safe_score(
                mtf
            ),

            "derivatives": self._safe_score(
                derivatives
            ),

            "market": self._get_market_score(
                market,
                direction,
            ),

            "ai": self._safe_score(
                ai
            ),
        }

        # ------------------------------------------------------
        # Directional adjustment
        # ------------------------------------------------------

        adjusted_scores = {

            "technical":
                self._directional_score(
                    raw_scores["technical"],
                    self._direction(
                        technical
                    ),
                    direction,
                ),

            "smc":
                raw_scores["smc"],

            "mtf":
                self._directional_score(
                    raw_scores["mtf"],
                    self._direction(
                        mtf
                    ),
                    direction,
                ),

            "derivatives":
                self._directional_score(
                    raw_scores["derivatives"],
                    self._direction(
                        derivatives
                    ),
                    direction,
                ),

            "market":
                raw_scores["market"],

            # AI is treated as a reviewer.
            # It is not directionally penalized here.
            "ai":
                raw_scores["ai"],
        }

        # ------------------------------------------------------
        # Weighted score
        # ------------------------------------------------------

        weighted_score = (
            self._calculate_weighted_score(
                adjusted_scores
            )
        )

        # ------------------------------------------------------
        # Confluence
        # ------------------------------------------------------

        component_directions = {

            "technical":
                self._direction(
                    technical
                ),

            "smc":
                str(
                    smc.get(
                        "preferred_direction",
                        "NEUTRAL",
                    )
                ).upper(),

            "mtf":
                self._direction(
                    mtf
                ),

            "derivatives":
                self._direction(
                    derivatives
                ),
        }

        confluence = (
            self._calculate_confluence(
                component_directions,
                direction,
            )
        )

        # ------------------------------------------------------
        # Warnings
        # ------------------------------------------------------

        warnings = (
            self._build_warnings(
                direction,
                confluence,
                derivatives,
                mtf,
                adjusted_scores,
            )
        )

        # ------------------------------------------------------
        # Grade
        # ------------------------------------------------------

        grade = self._get_grade(
            weighted_score
        )

        # ------------------------------------------------------
        # Signal State
        # ------------------------------------------------------

        state = self._get_state(
            weighted_score,
            confluence,
            direction,
            warnings,
        )

        # ------------------------------------------------------
        # Component availability
        # ------------------------------------------------------

        available_components = [
            name
            for name, score
            in adjusted_scores.items()
            if score is not None
        ]

        missing_components = [
            name
            for name, score
            in adjusted_scores.items()
            if score is None
        ]

        # ------------------------------------------------------
        # Result
        # ------------------------------------------------------

        result = {

            "direction":
                direction,

            "score":
                round(
                    weighted_score,
                    2,
                ),

            "grade":
                grade,

            "state":
                state,

            "confluence":
                round(
                    confluence,
                    2,
                ),

            "components": {

                name:
                    (
                        round(
                            score,
                            2,
                        )
                        if score is not None
                        else None
                    )

                for name, score
                in adjusted_scores.items()
            },

            "component_directions":
                component_directions,

            "available_components":
                available_components,

            "missing_components":
                missing_components,

            "warnings":
                warnings,

            "status":
                "SUCCESS",
        }

        logger.info(
            (
                "Fusion result | "
                "direction=%s | "
                "score=%.2f | "
                "grade=%s | "
                "state=%s | "
                "confluence=%.2f%%"
            ),
            direction,
            weighted_score,
            grade,
            state,
            confluence,
        )

        return result
