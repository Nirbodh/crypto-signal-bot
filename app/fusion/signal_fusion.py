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
        - Market Context
        - Optional AI reviewer score

    Design goals:
        - Never invent missing scores
        - Directional disagreement reduces quality
        - Neutral modules do not create confidence
        - Market context has limited influence
        - AI is optional and cannot create a signal by itself
        - Confluence measures directional agreement
        - Minimum evidence is required for strong candidates
        - Compatible with ScannerEngine output
    """

    # ==========================================================
    # Initialization
    # ==========================================================

    def __init__(
        self,
        weights: Optional[Dict[str, float]] = None,
        min_score: float = 70.0,
        min_confluence: float = 70.0,
        min_directional_components: int = 2,
    ) -> None:

        self.weights = weights or {
            "technical": 0.30,
            "smc": 0.30,
            "mtf": 0.20,
            "derivatives": 0.15,
            "market": 0.05,
        }

        self.min_score = float(min_score)
        self.min_confluence = float(min_confluence)
        self.min_directional_components = int(
            min_directional_components
        )

        self._validate_weights()

    # ==========================================================
    # Validation
    # ==========================================================

    def _validate_weights(self) -> None:
        """Validate configured fusion weights."""

        if not self.weights:

            raise ValueError(
                "Fusion weights cannot be empty."
            )

        total = 0.0

        for name, weight in self.weights.items():

            if not isinstance(
                weight,
                (int, float),
            ):

                raise TypeError(
                    f"Weight for '{name}' must be numeric."
                )

            if weight < 0:

                raise ValueError(
                    f"Weight for '{name}' cannot be negative."
                )

            total += float(weight)

        if total <= 0:

            raise ValueError(
                "At least one fusion weight must be greater than zero."
            )

    # ==========================================================
    # Safe helpers
    # ==========================================================

    @staticmethod
    def _safe_score(
        data: Any,
        default: Optional[float] = None,
    ) -> Optional[float]:
        """
        Safely extract score.

        Missing/invalid score remains None.
        No artificial score is created.
        """

        if not isinstance(data, dict):

            return default

        value = data.get("score")

        if value is None:

            return default

        try:

            value = float(value)

        except (
            TypeError,
            ValueError,
        ):

            return default

        if value != value:  # NaN

            return default

        return max(
            0.0,
            min(
                100.0,
                value,
            ),
        )

    @staticmethod
    def _direction(
        data: Any,
    ) -> str:
        """
        Normalize module direction.
        """

        if not isinstance(data, dict):

            return "NEUTRAL"

        direction = str(
            data.get(
                "direction",
                data.get(
                    "trend",
                    data.get(
                        "preferred_direction",
                        "NEUTRAL",
                    ),
                ),
            )
        ).upper().strip()

        if direction in {
            "BULLISH",
            "LONG",
            "BUY",
        }:

            return "BULLISH"

        if direction in {
            "BEARISH",
            "SHORT",
            "SELL",
        }:

            return "BEARISH"

        return "NEUTRAL"

    # ==========================================================
    # SMC Direction
    # ==========================================================

    @classmethod
    def _smc_direction(
        cls,
        smc: Dict[str, Any],
    ) -> str:
        """
        Extract SMC directional bias.

        Supports:
            preferred_direction
            direction
            trend
        """

        if not isinstance(smc, dict):

            return "NEUTRAL"

        direction = str(
            smc.get(
                "preferred_direction",
                smc.get(
                    "direction",
                    smc.get(
                        "trend",
                        "NEUTRAL",
                    ),
                ),
            )
        ).upper().strip()

        if direction in {
            "BULLISH",
            "LONG",
            "BUY",
        }:

            return "BULLISH"

        if direction in {
            "BEARISH",
            "SHORT",
            "SELL",
        }:

            return "BEARISH"

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

        Supported structures:

            {
                "preferred_direction": "BULLISH",
                "bullish": {
                    "score": 82
                }
            }

        or:

            {
                "score": 82
            }
        """

        if not isinstance(smc, dict):

            return None

        if direction == "BULLISH":

            bullish = smc.get(
                "bullish"
            )

            score = self._safe_score(
                bullish
            )

            if score is not None:

                return score

        elif direction == "BEARISH":

            bearish = smc.get(
                "bearish"
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
        Convert market context into a limited directional score.

        Market context can influence the final quality,
        but it cannot dominate the technical/SMC/MTF evidence.
        """

        if not isinstance(
            market,
            dict,
        ):

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

            change = market.get(
                "change_24h"
            )

        try:

            change = float(
                change
            )

        except (
            TypeError,
            ValueError,
        ):

            return None

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
    # Directional Adjustment
    # ==========================================================

    @staticmethod
    def _directional_score(
        score: Optional[float],
        component_direction: str,
        target_direction: str,
    ) -> Optional[float]:
        """
        Apply directional consistency penalty.

        Same direction:
            100%

        Neutral:
            85%

        Opposite:
            55%
        """

        if score is None:

            return None

        if target_direction == "NEUTRAL":

            return score

        if component_direction == target_direction:

            return score

        if component_direction == "NEUTRAL":

            return score * 0.85

        return score * 0.55

    # ==========================================================
    # Weighted Score
    # ==========================================================

    def _calculate_weighted_score(
        self,
        component_scores: Dict[
            str,
            Optional[float],
        ],
    ) -> float:
        """
        Weighted average using ONLY available components.

        Missing modules receive no score and no weight.
        """

        weighted_total = 0.0
        active_weight = 0.0

        for component, score in (
            component_scores.items()
        ):

            if score is None:

                continue

            weight = float(
                self.weights.get(
                    component,
                    0.0,
                )
            )

            if weight <= 0:

                continue

            weighted_total += (
                score * weight
            )

            active_weight += weight

        if active_weight <= 0:

            return 0.0

        result = (
            weighted_total
            / active_weight
        )

        return max(
            0.0,
            min(
                100.0,
                result,
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
        Determine primary directional bias.

        Priority:
            Technical
            MTF
            Derivatives

        SMC acts as tie-breaker.
        """

        directional_sources = [
            (
                "technical",
                self._direction(
                    technical
                ),
            ),
            (
                "mtf",
                self._direction(
                    mtf
                ),
            ),
            (
                "derivatives",
                self._direction(
                    derivatives
                ),
            ),
        ]

        bullish = 0
        bearish = 0

        for _, direction in (
            directional_sources
        ):

            if direction == "BULLISH":

                bullish += 1

            elif direction == "BEARISH":

                bearish += 1

        if bullish > bearish:

            return "BULLISH"

        if bearish > bullish:

            return "BEARISH"

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
        Calculate directional agreement.

        Only:
            Technical
            SMC
            MTF
            Derivatives

        participate.

        Neutral components are ignored.
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

        for component in (
            directional_components
        ):

            direction = (
                component_directions.get(
                    component,
                    "NEUTRAL",
                )
            )

            if direction == "NEUTRAL":

                continue

            active += 1

            if direction == target_direction:

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
        component_scores: Dict[
            str,
            Optional[float],
        ],
        component_directions: Dict[
            str,
            str,
        ],
    ) -> list:
        """
        Build warnings without inventing data.
        """

        warnings = []

        # ------------------------------------------------------
        # Directional evidence count
        # ------------------------------------------------------

        directional_components = (
            "technical",
            "smc",
            "mtf",
            "derivatives",
        )

        active_directional = [
            component
            for component in directional_components
            if component_directions.get(
                component,
                "NEUTRAL",
            )
            != "NEUTRAL"
        ]

        if len(active_directional) < (
            self.min_directional_components
        ):

            warnings.append(
                "Insufficient directional evidence"
            )

        # ------------------------------------------------------
        # Confluence
        # ------------------------------------------------------

        if (
            direction != "NEUTRAL"
            and confluence < 50
        ):

            warnings.append(
                "Strong directional disagreement "
                "between analysis modules"
            )

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
                + ", ".join(
                    missing
                )
            )

        # ------------------------------------------------------
        # Derivatives funding
        # ------------------------------------------------------

        funding = derivatives.get(
            "funding",
            {},
        )

        if isinstance(
            funding,
            dict,
        ):

            funding_risk = str(
                funding.get(
                    "risk",
                    "",
                )
            ).upper()

            if funding_risk == "HIGH":

                warnings.append(
                    "Extreme funding / "
                    "crowded positioning"
                )

        # ------------------------------------------------------
        # Alternative funding structures
        # ------------------------------------------------------

        funding_rate = (
            derivatives.get(
                "funding_rate"
            )
        )

        try:

            if funding_rate is not None:

                funding_rate = float(
                    funding_rate
                )

                # Extremely positive or negative
                # funding indicates crowding.

                if abs(
                    funding_rate
                ) >= 0.01:

                    warnings.append(
                        "Extreme funding rate detected"
                    )

        except (
            TypeError,
            ValueError,
        ):

            pass

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

        for name, score in (
            component_scores.items()
        ):

            if (
                score is not None
                and score < 35
            ):

                warnings.append(
                    f"Weak {name} component"
                )

        # ------------------------------------------------------
        # Remove duplicate warnings
        # ------------------------------------------------------

        return list(
            dict.fromkeys(
                warnings
            )
        )

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
    # State
    # ==========================================================

    def _get_state(
        self,
        score: float,
        confluence: float,
        direction: str,
        warnings: list,
        directional_component_count: int,
    ) -> str:
        """
        Determine setup state.

        TRADE_CANDIDATE requires:
            score >= min_score
            confluence >= min_confluence
            valid direction
            enough directional evidence
            no critical funding warning

        WATCH requires:
            score >= min_score
            confluence >= 60

        WEAK_SETUP:
            score >= 60

        Otherwise:
            NO_CLEAR_SETUP
        """

        if direction == "NEUTRAL":

            return "NO_CLEAR_SETUP"

        critical_warning = any(
            (
                "Extreme funding"
                in warning
            )
            or (
                "crowded positioning"
                in warning
            )
            for warning in warnings
        )

        # Strong candidate.

        if (
            score >= self.min_score
            and confluence >= self.min_confluence
            and directional_component_count
            >= self.min_directional_components
            and not critical_warning
        ):

            return "TRADE_CANDIDATE"

        # Watch.

        if (
            score >= self.min_score
            and confluence >= 60
        ):

            return "WATCH"

        # Weak.

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
        """
        Main fusion method.

        AI is accepted for compatibility but does not participate
        in the primary quantitative score.

        Gemini remains an independent reviewer in ScannerEngine.
        """

        technical = (
            technical
            if isinstance(
                technical,
                dict,
            )
            else {}
        )

        smc = (
            smc
            if isinstance(
                smc,
                dict,
            )
            else {}
        )

        mtf = (
            mtf
            if isinstance(
                mtf,
                dict,
            )
            else {}
        )

        derivatives = (
            derivatives
            if isinstance(
                derivatives,
                dict,
            )
            else {}
        )

        market = (
            market
            if isinstance(
                market,
                dict,
            )
            else {}
        )

        ai = (
            ai
            if isinstance(
                ai,
                dict,
            )
            else {}
        )

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
        }

        # AI score kept separately.
        ai_score = self._safe_score(
            ai
        )

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

            "market":
                "NEUTRAL",
        }

        # ======================================================
        # Directional Adjustments
        # ======================================================

        adjusted_scores = {}

        for component in (
            "technical",
            "smc",
            "mtf",
            "derivatives",
        ):

            adjusted_scores[
                component
            ] = self._directional_score(
                raw_scores.get(
                    component
                ),
                component_directions.get(
                    component,
                    "NEUTRAL",
                ),
                direction,
            )

        # Market does not require directional penalty because
        # _get_market_score already evaluates it directionally.

        adjusted_scores[
            "market"
        ] = raw_scores.get(
            "market"
        )

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
        # Directional Evidence
        # ======================================================

        directional_component_count = sum(
            1
            for component in (
                "technical",
                "smc",
                "mtf",
                "derivatives",
            )
            if component_directions.get(
                component,
                "NEUTRAL",
            )
            != "NEUTRAL"
        )

        # ======================================================
        # Warnings
        # ======================================================

        warnings = (
            self._build_warnings(
                direction=direction,
                confluence=confluence,
                derivatives=derivatives,
                mtf=mtf,
                component_scores=adjusted_scores,
                component_directions=component_directions,
            )
        )

        # ======================================================
        # Grade
        # ======================================================

        grade = self._get_grade(
            weighted_score
        )

        # ======================================================
        # State
        # ======================================================

        state = self._get_state(
            score=weighted_score,
            confluence=confluence,
            direction=direction,
            warnings=warnings,
            directional_component_count=(
                directional_component_count
            ),
        )

        # ======================================================
        # Availability
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
        # Quality Flag
        # ======================================================

        quality_pass = bool(
            (
                weighted_score
                >= self.min_score
            )
            and (
                direction
                != "NEUTRAL"
            )
            and (
                confluence
                >= self.min_confluence
            )
            and (
                directional_component_count
                >= self.min_directional_components
            )
        )

        # ======================================================
        # Result
        # ======================================================

        result = {
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

            "quality_pass": quality_pass,

            "directional_evidence_count": (
                directional_component_count
            ),

            "components": {
                name: (
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
                name: (
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

            # AI is informational/reviewer data only.
            "ai": {
                "available": (
                    ai_score is not None
                ),
                "score": (
                    round(
                        ai_score,
                        2,
                    )
                    if ai_score is not None
                    else None
                ),
            },

            "status": "SUCCESS",
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
                "confluence=%.2f%% | "
                "directional_evidence=%s/4 | "
                "quality_pass=%s"
            ),
            direction,
            weighted_score,
            grade,
            state,
            confluence,
            directional_component_count,
            quality_pass,
        )

        return result
