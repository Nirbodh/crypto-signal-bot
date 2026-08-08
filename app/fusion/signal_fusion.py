import logging
from typing import Any, Dict, Optional


logger = logging.getLogger("crypto-signal-bot")


class SignalFusionEngine:
    """
    Production Signal Fusion Engine.

    Combines:

        - Technical Analysis
        - Smart Money Concepts (SMC)
        - Multi-Timeframe Analysis (MTF)
        - Derivatives
        - Market / Fundamental Data
        - AI Review

    IMPORTANT
    ---------
    The score measures SETUP QUALITY.
    It does NOT predict future price movement.

    Market-cap is intentionally NOT used here as a signal filter.

    Therefore:
        - Large-cap coins can qualify.
        - Mid-cap coins can qualify.
        - Low-cap coins can qualify.

    A low-cap coin must still demonstrate sufficient:
        - technical quality
        - SMC quality
        - MTF alignment
        - derivatives quality
        - market context

    The purpose of this engine is to prevent good setups from
    being rejected simply because the asset is not BTC/ETH/XRP/SOL
    class market-cap.

    Design principles:
        1. Missing data must not receive artificial scores.
        2. Directional disagreement must reduce score.
        3. Neutral modules should not create fake confidence.
        4. AI remains a reviewer, not the primary signal generator.
        5. Confluence measures directional agreement only.
        6. Score >= 70 is a QUALITY threshold, not a market-cap filter.
        7. Strong trade candidates require both quality and confluence.
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

        Weights are normalized dynamically using only the
        components that are actually available.
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
        Safely extract a score from a module result.

        Never invents a score when data is missing.
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
        Normalize component direction.
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
    # SMC Direction
    # ==========================================================

    @staticmethod
    def _smc_direction(
        smc: Dict[str, Any],
    ) -> str:
        """
        Extract SMC preferred direction safely.
        """

        if not isinstance(smc, dict):

            return "NEUTRAL"

        direction = str(
            smc.get(
                "preferred_direction",
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

        Supports:

            smc["bullish"]["score"]
            smc["bearish"]["score"]

        and direct:

            smc["score"]
        """

        if not isinstance(smc, dict):

            return None

        if direction == "BULLISH":

            bullish = smc.get(
                "bullish",
                {},
            )

            score = self._safe_score(
                bullish
            )

            if score is not None:

                return score

        elif direction == "BEARISH":

            bearish = smc.get(
                "bearish",
                {},
            )

            score = self._safe_score(
                bearish
            )

            if score is not None:

                return score

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
        Calculate directional market-context score.

        Uses 24h momentum when available.

        IMPORTANT:
        Market data is not allowed to dominate the fusion.
        """

        if not isinstance(market, dict):

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

        if change is None:

            # Try common alternative locations.

            change = market.get(
                "change_24h"
            )

        try:

            change = float(change)

        except (
            TypeError,
            ValueError,
        ):

            return None

        score = 50.0

        # ------------------------------------------------------
        # Bullish market direction
        # ------------------------------------------------------

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

        # ------------------------------------------------------
        # Bearish market direction
        # ------------------------------------------------------

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
    # Directional Score Adjustment
    # ==========================================================

    @staticmethod
    def _directional_score(
        score: Optional[float],
        component_direction: str,
        target_direction: str,
    ) -> Optional[float]:
        """
        Adjust a component score according to direction.

        Same direction:
            100% of score.

        Neutral:
            Mild reduction.

        Opposite:
            Strong but controlled penalty.

        The previous 0.35 multiplier was intentionally too
        aggressive for mixed-market conditions. It could cause
        a genuinely strong low-cap setup to collapse even when
        most important modules agreed.
        """

        if score is None:

            return None

        if target_direction == "NEUTRAL":

            return score

        if component_direction == target_direction:

            return score

        if component_direction == "NEUTRAL":

            return score * 0.85

        # Opposite direction.

        return score * 0.55

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
        Determine primary direction.

        Priority:

            1. Technical
            2. MTF
            3. Derivatives

        SMC is used as a tie-breaker.

        Market-cap is NOT considered.
        """

        votes = []

        for source in (
            technical,
            mtf,
            derivatives,
        ):

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

        # Tie-breaker: SMC.

        smc_direction = (
            self._smc_direction(
                smc
            )
        )

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

        Only directional components participate:

            technical
            smc
            mtf
            derivatives

        Market and AI do NOT participate because they are not
        reliable directional voting engines in this fusion layer.

        Neutral components are ignored.

        Example:

            Technical = Bullish
            SMC       = Bullish
            MTF       = Bullish
            Deriv     = Bullish

            => 100% confluence

        Example:

            Technical = Bullish
            SMC       = Bullish
            MTF       = Bearish
            Deriv     = Bullish

            => 75% confluence
        """

        if target_direction == "NEUTRAL":

            return 0.0

        directional_components = (
            "technical",
            "smc",
            "mtf",
            "derivatives",
        )

        active = 0
        aligned = 0

        for component in directional_components:

            component_direction = (
                component_directions.get(
                    component,
                    "NEUTRAL",
                )
            )

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
        Build quality and risk warnings.
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
                "Strong directional disagreement "
                "between analysis modules"
            )

        # ------------------------------------------------------
        # Moderate confluence
        # ------------------------------------------------------

        elif (
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
        # Funding risk
        # ------------------------------------------------------

        funding = derivatives.get(
            "funding",
            {},
        )

        if isinstance(
            funding,
            dict,
        ):

            if str(
                funding.get(
                    "risk",
                    "",
                )
            ).upper() == "HIGH":

                warnings.append(
                    "Extreme funding / "
                    "crowded positioning"
                )

        # ------------------------------------------------------
        # MTF entry timing
        # ------------------------------------------------------

        entry_timing = str(
            mtf.get(
                "entry_timing",
                "",
            )
        ).upper()

        if entry_timing == "CONTRARY":

            warnings.append(
                "Lower timeframe is currently "
                "against primary direction"
            )

        # ------------------------------------------------------
        # Weak components
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
        Determine final setup state.

        IMPORTANT:

        Score >= 70 is NOT enough for a TRADE_CANDIDATE.

        TRADE_CANDIDATE:
            Score >= 70
            Confluence >= 70%
            Valid direction
            No critical funding warning

        WATCH:
            Score >= 70
            Confluence >= 60%

        WEAK_SETUP:
            Score >= 60

        NO_CLEAR_SETUP:
            Everything else.
        """

        if direction == "NEUTRAL":

            return "NO_CLEAR_SETUP"

        critical_warning = any(
            "Extreme funding"
            in warning
            for warning in warnings
        )

        # ------------------------------------------------------
        # Strong candidate
        # ------------------------------------------------------

        if (
            score >= 70
            and confluence >= 70
            and not critical_warning
        ):

            return "TRADE_CANDIDATE"

        # ------------------------------------------------------
        # Watch
        # ------------------------------------------------------

        if (
            score >= 70
            and confluence >= 60
        ):

            return "WATCH"

        # ------------------------------------------------------
        # Weak setup
        # ------------------------------------------------------

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

        # ======================================================
        # Primary Direction
        # ======================================================

        direction = (
            self._determine_primary_direction(
                technical,
                smc,
                mtf,
                derivatives,
            )
        )

        # ======================================================
        # Raw Scores
        # ======================================================

        raw_scores = {

            "technical":
                self._safe_score(
                    technical
                ),

            "smc":
                self._get_smc_score(
                    smc,
                    direction,
                ),

            "mtf":
                self._safe_score(
                    mtf
                ),

            "derivatives":
                self._safe_score(
                    derivatives
                ),

            "market":
                self._get_market_score(
                    market,
                    direction,
                ),

            "ai":
                self._safe_score(
                    ai
                ),
        }

        # ======================================================
        # Component Directions
        # ======================================================

        component_directions = {

            "technical":
                self._direction(
                    technical
                ),

            "smc":
                self._smc_direction(
                    smc
                ),

            "mtf":
                self._direction(
                    mtf
                ),

            "derivatives":
                self._direction(
                    derivatives
                ),

            # Market is intentionally not a directional
            # confluence vote.
            "market":
                "NEUTRAL",

            # AI is a reviewer, not a directional vote.
            "ai":
                "NEUTRAL",
        }

        # ======================================================
        # Directional Score Adjustment
        # ======================================================

        adjusted_scores = {

            "technical":
                self._directional_score(
                    raw_scores["technical"],
                    component_directions[
                        "technical"
                    ],
                    direction,
                ),

            "smc":
                self._directional_score(
                    raw_scores["smc"],
                    component_directions[
                        "smc"
                    ],
                    direction,
                ),

            "mtf":
                self._directional_score(
                    raw_scores["mtf"],
                    component_directions[
                        "mtf"
                    ],
                    direction,
                ),

            "derivatives":
                self._directional_score(
                    raw_scores["derivatives"],
                    component_directions[
                        "derivatives"
                    ],
                    direction,
                ),

            "market":
                raw_scores["market"],

            # AI remains an independent reviewer score.
            "ai":
                raw_scores["ai"],
        }

        # ======================================================
        # Weighted Score
        # ======================================================

        weighted_score = (
            self._calculate_weighted_score(
                adjusted_scores
            )
        )

        # ======================================================
        # Confluence
        # ======================================================

        confluence = (
            self._calculate_confluence(
                component_directions,
                direction,
            )
        )

        # ======================================================
        # Warnings
        # ======================================================

        warnings = (
            self._build_warnings(
                direction,
                confluence,
                derivatives,
                mtf,
                adjusted_scores,
            )
        )

        # ======================================================
        # Grade
        # ======================================================

        grade = self._get_grade(
            weighted_score
        )

        # ======================================================
        # Signal State
        # ======================================================

        state = self._get_state(
            weighted_score,
            confluence,
            direction,
            warnings,
        )

        # ======================================================
        # Component Availability
        # ======================================================

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

        # ======================================================
        # Result
        # ======================================================

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

            "raw_components": {

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
                in raw_scores.items()
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

        # ======================================================
        # Logging
        # ======================================================

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
