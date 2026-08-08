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
        - AI Review

    IMPORTANT
    ----------
    This engine measures SETUP QUALITY.

    It does NOT predict future price movement.

    Core principles:
        1. Missing data never receives a fake score.
        2. Directional disagreement reduces quality.
        3. Neutral modules do not create fake confidence.
        4. AI is a reviewer, not a primary signal generator.
        5. Market context has limited influence.
        6. Confluence is based only on directional engines.
        7. Minimum evidence is required before a candidate.
        8. Score and confluence are separate concepts.
        9. Scanner-compatible output is always returned.
    """

    # ==========================================================
    # Configuration
    # ==========================================================

    DEFAULT_WEIGHTS = {
        "technical": 0.25,
        "smc": 0.25,
        "mtf": 0.20,
        "derivatives": 0.15,
        "market": 0.10,
        "ai": 0.05,
    }

    DIRECTIONAL_COMPONENTS = (
        "technical",
        "smc",
        "mtf",
        "derivatives",
    )

    # Minimum directional evidence required.
    MIN_DIRECTIONAL_COMPONENTS = 2

    # ==========================================================
    # Initialization
    # ==========================================================

    def __init__(
        self,
        weights: Optional[Dict[str, float]] = None,
    ) -> None:

        self.weights = dict(
            weights
            if weights is not None
            else self.DEFAULT_WEIGHTS
        )

        self._validate_weights()

    # ==========================================================
    # Weight Validation
    # ==========================================================

    def _validate_weights(self) -> None:

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

        total = sum(
            float(weight)
            for weight in self.weights.values()
        )

        if total <= 0:
            raise ValueError(
                "At least one fusion weight must be greater than zero."
            )

    # ==========================================================
    # Safe Dictionary
    # ==========================================================

    @staticmethod
    def _safe_dict(
        data: Any,
    ) -> Dict[str, Any]:

        if isinstance(data, dict):
            return data

        return {}

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

        IMPORTANT:
        Missing score remains None.
        No artificial 50 score is generated.
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

        if value != value:
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
        Normalize engine direction.

        Supported:
            BULLISH
            BEARISH
            NEUTRAL
            UNKNOWN
        """

        if not isinstance(data, dict):
            return "UNKNOWN"

        direction = str(
            data.get(
                "direction",
                "UNKNOWN",
            )
        ).upper().strip()

        if direction in {
            "BULLISH",
            "BEARISH",
            "NEUTRAL",
            "UNKNOWN",
        }:
            return direction

        return "UNKNOWN"

    # ==========================================================
    # SMC Direction
    # ==========================================================

    @staticmethod
    def _smc_direction(
        smc: Dict[str, Any],
    ) -> str:

        if not isinstance(smc, dict):
            return "UNKNOWN"

        direction = str(
            smc.get(
                "preferred_direction",
                smc.get(
                    "direction",
                    "UNKNOWN",
                ),
            )
        ).upper().strip()

        if direction in {
            "BULLISH",
            "BEARISH",
            "NEUTRAL",
            "UNKNOWN",
        }:
            return direction

        return "UNKNOWN"

    # ==========================================================
    # SMC Score
    # ==========================================================

    def _get_smc_score(
        self,
        smc: Dict[str, Any],
        direction: str,
    ) -> Optional[float]:
        """
        Supports:

            smc["bullish"]["score"]
            smc["bearish"]["score"]

        and:

            smc["score"]
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
    # Market Context Score
    # ==========================================================

    def _get_market_score(
        self,
        market: Dict[str, Any],
        direction: str,
    ) -> Optional[float]:
        """
        Market context is intentionally limited.

        It starts from neutral 50 only AFTER valid
        market momentum data exists.

        24h movement contributes at most +/-20 points.
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
            change = float(change)

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
    # Directional Score Adjustment
    # ==========================================================

    @staticmethod
    def _directional_score(
        score: Optional[float],
        component_direction: str,
        target_direction: str,
    ) -> Optional[float]:
        """
        Direction-aware score adjustment.

        Same:
            100%

        Neutral:
            85%

        Opposite:
            55%

        Unknown:
            No score contribution.
        """

        if score is None:
            return None

        if target_direction not in {
            "BULLISH",
            "BEARISH",
        }:
            return score

        if component_direction == target_direction:
            return score

        if component_direction == "NEUTRAL":
            return score * 0.85

        if component_direction == "UNKNOWN":
            return None

        # Opposite direction.
        return score * 0.55

    # ==========================================================
    # Weighted Fusion
    # ==========================================================

    def _calculate_weighted_score(
        self,
        component_scores: Dict[
            str,
            Optional[float],
        ],
    ) -> float:
        """
        Calculate weighted score using ONLY available components.

        Missing components are removed from the denominator.
        """

        weighted_total = 0.0
        active_weight = 0.0

        for component, score in component_scores.items():

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
                float(score)
                * weight
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

        Directional engines:
            Technical
            MTF
            Derivatives
            SMC tie-breaker

        At least two directional votes are preferred.

        If only one engine provides direction, the result
        becomes UNKNOWN rather than pretending there is
        strong market consensus.
        """

        sources = {
            "technical": self._direction(
                technical
            ),
            "mtf": self._direction(
                mtf
            ),
            "derivatives": self._direction(
                derivatives
            ),
        }

        votes = [
            direction
            for direction in sources.values()
            if direction in {
                "BULLISH",
                "BEARISH",
            }
        ]

        bullish_votes = votes.count(
            "BULLISH"
        )

        bearish_votes = votes.count(
            "BEARISH"
        )

        # ------------------------------------------------------
        # Clear majority
        # ------------------------------------------------------

        if bullish_votes > bearish_votes:
            return "BULLISH"

        if bearish_votes > bullish_votes:
            return "BEARISH"

        # ------------------------------------------------------
        # No majority -> SMC tie-breaker
        # ------------------------------------------------------

        smc_direction = (
            self._smc_direction(
                smc
            )
        )

        if smc_direction in {
            "BULLISH",
            "BEARISH",
        }:

            # SMC can break a tie only when there is
            # at least one directional vote.
            if votes:
                return smc_direction

        return "NEUTRAL"

    # ==========================================================
    # Directional Evidence Count
    # ==========================================================

    @staticmethod
    def _count_directional_evidence(
        component_directions: Dict[str, str],
    ) -> int:

        return sum(
            1
            for component in (
                "technical",
                "smc",
                "mtf",
                "derivatives",
            )
            if component_directions.get(
                component
            ) in {
                "BULLISH",
                "BEARISH",
            }
        )

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

        Neutral / Unknown modules are ignored.
        """

        if target_direction not in {
            "BULLISH",
            "BEARISH",
        }:
            return 0.0

        active = 0
        aligned = 0

        for component in (
            "technical",
            "smc",
            "mtf",
            "derivatives",
        ):

            component_direction = (
                component_directions.get(
                    component,
                    "UNKNOWN",
                )
            )

            if component_direction not in {
                "BULLISH",
                "BEARISH",
            }:
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
    # Minimum Evidence
    # ==========================================================

    def _minimum_evidence_ok(
        self,
        component_directions: Dict[str, str],
        direction: str,
    ) -> bool:

        if direction not in {
            "BULLISH",
            "BEARISH",
        }:
            return False

        evidence_count = (
            self._count_directional_evidence(
                component_directions
            )
        )

        if (
            evidence_count
            < self.MIN_DIRECTIONAL_COMPONENTS
        ):
            return False

        aligned_count = sum(
            1
            for component in (
                "technical",
                "smc",
                "mtf",
                "derivatives",
            )
            if component_directions.get(
                component
            )
            == direction
        )

        return aligned_count >= 2

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

        warnings = []

        # ------------------------------------------------------
        # Minimum evidence
        # ------------------------------------------------------

        evidence_count = (
            self._count_directional_evidence(
                component_directions
            )
        )

        if evidence_count < 2:

            warnings.append(
                "Insufficient directional evidence"
            )

        # ------------------------------------------------------
        # Directional disagreement
        # ------------------------------------------------------

        if (
            direction in {
                "BULLISH",
                "BEARISH",
            }
            and confluence < 50
        ):

            warnings.append(
                "Strong directional disagreement "
                "between analysis modules"
            )

        elif (
            direction in {
                "BULLISH",
                "BEARISH",
            }
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

            risk = str(
                funding.get(
                    "risk",
                    "",
                )
            ).upper()

            if risk == "HIGH":

                warnings.append(
                    "Extreme funding / "
                    "crowded positioning"
                )

        # Some derivatives engines may expose
        # funding risk at top-level.
        elif str(
            derivatives.get(
                "funding_risk",
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

        elif entry_timing == "UNAVAILABLE":

            warnings.append(
                "Entry timeframe unavailable"
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
    # State
    # ==========================================================

    @staticmethod
    def _get_state(
        score: float,
        confluence: float,
        direction: str,
        warnings: list,
        minimum_evidence_ok: bool,
    ) -> str:
        """
        Final setup state.

        TRADE_CANDIDATE:
            score >= 70
            confluence >= 70
            valid direction
            minimum evidence
            no critical funding warning

        WATCH:
            score >= 70
            confluence >= 60
            valid direction
            minimum evidence

        WEAK_SETUP:
            score >= 60
            valid direction

        NO_CLEAR_SETUP:
            everything else
        """

        if direction not in {
            "BULLISH",
            "BEARISH",
        }:
            return "NO_CLEAR_SETUP"

        if not minimum_evidence_ok:
            return "NO_CLEAR_SETUP"

        critical_warning = any(
            "Extreme funding"
            in str(warning)
            for warning in warnings
        )

        if (
            score >= 70
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

        technical = self._safe_dict(
            technical
        )

        smc = self._safe_dict(
            smc
        )

        mtf = self._safe_dict(
            mtf
        )

        derivatives = self._safe_dict(
            derivatives
        )

        market = self._safe_dict(
            market
        )

        ai = self._safe_dict(
            ai
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

        # ======================================================
        # Component Directions
        # ======================================================

        component_directions = {
            "technical": self._direction(
                technical
            ),

            "smc": self._smc_direction(
                smc
            ),

            "mtf": self._direction(
                mtf
            ),

            "derivatives": self._direction(
                derivatives
            ),

            # Market is context only.
            "market": "NEUTRAL",

            # AI is reviewer only.
            "ai": "NEUTRAL",
        }

        # ======================================================
        # Adjusted Scores
        # ======================================================

        adjusted_scores = {
            "technical": self._directional_score(
                raw_scores["technical"],
                component_directions[
                    "technical"
                ],
                direction,
            ),

            "smc": self._directional_score(
                raw_scores["smc"],
                component_directions[
                    "smc"
                ],
                direction,
            ),

            "mtf": self._directional_score(
                raw_scores["mtf"],
                component_directions[
                    "mtf"
                ],
                direction,
            ),

            "derivatives": self._directional_score(
                raw_scores["derivatives"],
                component_directions[
                    "derivatives"
                ],
                direction,
            ),

            "market": raw_scores[
                "market"
            ],

            "ai": raw_scores[
                "ai"
            ],
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
        # Minimum Evidence
        # ======================================================

        minimum_evidence_ok = (
            self._minimum_evidence_ok(
                component_directions,
                direction,
            )
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
        # Evidence Penalty
        # ======================================================
        #
        # If only two modules are available, the weighted
        # score is still valid, but we prevent it from looking
        # like a fully confirmed setup.
        #

        directional_evidence = (
            self._count_directional_evidence(
                component_directions
            )
        )

        if directional_evidence == 2:

            weighted_score *= 0.95

        elif directional_evidence == 1:

            weighted_score *= 0.85

        weighted_score = max(
            0.0,
            min(
                100.0,
                weighted_score,
            ),
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
            minimum_evidence_ok=minimum_evidence_ok,
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
        # Status
        # ======================================================

        if (
            not available_components
        ):

            status = "UNAVAILABLE"

        else:

            status = "SUCCESS"

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

            "minimum_evidence": (
                minimum_evidence_ok
            ),

            "directional_evidence": (
                directional_evidence
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

            "status":
                status,
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
                "evidence=%s"
            ),
            direction,
            weighted_score,
            grade,
            state,
            confluence,
            directional_evidence,
        )

        return result
