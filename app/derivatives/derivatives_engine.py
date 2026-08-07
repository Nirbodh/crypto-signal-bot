import logging
from typing import Any, Dict, List, Optional


logger = logging.getLogger("crypto-signal-bot")


class DerivativesEngine:
    """
    Futures / derivatives context engine.

    Uses:
    - Open Interest
    - Funding Rate
    - Long/Short information
    - Liquidations

    This engine does NOT generate a final trade signal.

    It converts derivatives information into:
        bullish evidence
        bearish evidence
        warnings
        context score
    """

    def __init__(
        self,
        funding_neutral: float = 0.01,
        funding_extreme: float = 0.05,
    ):
        # Values are percentages.
        #
        # Example:
        # 0.01 = 0.01%
        # 0.05 = 0.05%

        self.funding_neutral = (
            funding_neutral
        )

        self.funding_extreme = (
            funding_extreme
        )

    # ==========================================================
    # Safe number conversion
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
    # Open Interest
    # ==========================================================

    def analyze_open_interest(
        self,
        current_oi: Any,
        previous_oi: Any,
        price_change_pct: Any = None,
    ) -> Dict[str, Any]:

        current = self._number(
            current_oi
        )

        previous = self._number(
            previous_oi
        )

        price_change = self._number(
            price_change_pct
        )

        result = {
            "status": "UNKNOWN",
            "change_pct": None,
            "interpretation": (
                "Insufficient OI data"
            ),
        }

        if (
            current is None
            or previous is None
            or previous == 0
        ):

            return result

        change_pct = (
            (
                current - previous
            )
            / previous
        ) * 100

        result["change_pct"] = round(
            change_pct,
            4,
        )

        # ------------------------------------------------------
        # OI increasing
        # ------------------------------------------------------

        if change_pct > 2:

            result["status"] = (
                "INCREASING"
            )

            if (
                price_change is not None
                and price_change > 0
            ):

                result[
                    "interpretation"
                ] = (
                    "OI rising with price - "
                    "bullish participation"
                )

            elif (
                price_change is not None
                and price_change < 0
            ):

                result[
                    "interpretation"
                ] = (
                    "OI rising while price falls - "
                    "bearish participation"
                )

            else:

                result[
                    "interpretation"
                ] = (
                    "OI increasing without "
                    "clear price confirmation"
                )

        # ------------------------------------------------------
        # OI decreasing
        # ------------------------------------------------------

        elif change_pct < -2:

            result["status"] = (
                "DECREASING"
            )

            if (
                price_change is not None
                and price_change > 0
            ):

                result[
                    "interpretation"
                ] = (
                    "Price rising while OI falls - "
                    "possible short covering"
                )

            elif (
                price_change is not None
                and price_change < 0
            ):

                result[
                    "interpretation"
                ] = (
                    "Price falling while OI falls - "
                    "possible long liquidation"
                )

            else:

                result[
                    "interpretation"
                ] = (
                    "OI decreasing"
                )

        else:

            result["status"] = (
                "STABLE"
            )

            result[
                "interpretation"
            ] = (
                "OI relatively stable"
            )

        return result

    # ==========================================================
    # Funding Rate
    # ==========================================================

    def analyze_funding(
        self,
        funding_rate: Any,
    ) -> Dict[str, Any]:

        funding = self._number(
            funding_rate
        )

        if funding is None:

            return {
                "status": "UNKNOWN",
                "direction": "UNKNOWN",
                "risk": "UNKNOWN",
                "interpretation": (
                    "Funding data unavailable"
                ),
            }

        # Positive funding:
        # longs pay shorts.

        if funding > self.funding_extreme:

            return {
                "status": "EXTREME",
                "direction": "BULLISH_BIAS",
                "risk": "HIGH",
                "interpretation": (
                    "Crowded long positioning"
                ),
            }

        if funding > self.funding_neutral:

            return {
                "status": "POSITIVE",
                "direction": "BULLISH_BIAS",
                "risk": "MODERATE",
                "interpretation": (
                    "Longs dominate funding"
                ),
            }

        # Negative funding:
        # shorts pay longs.

        if funding < -self.funding_extreme:

            return {
                "status": "EXTREME",
                "direction": "BEARISH_BIAS",
                "risk": "HIGH",
                "interpretation": (
                    "Crowded short positioning"
                ),
            }

        if funding < -self.funding_neutral:

            return {
                "status": "NEGATIVE",
                "direction": "BEARISH_BIAS",
                "risk": "MODERATE",
                "interpretation": (
                    "Shorts dominate funding"
                ),
            }

        return {
            "status": "NEUTRAL",
            "direction": "NEUTRAL",
            "risk": "LOW",
            "interpretation": (
                "Funding relatively balanced"
            ),
        }

    # ==========================================================
    # Long / Short Ratio
    # ==========================================================

    def analyze_long_short_ratio(
        self,
        ratio: Any,
    ) -> Dict[str, Any]:

        value = self._number(
            ratio
        )

        if value is None:

            return {
                "status": "UNKNOWN",
                "direction": "UNKNOWN",
                "interpretation": (
                    "Long/short ratio unavailable"
                ),
            }

        if value >= 1.5:

            return {
                "status": "LONG_HEAVY",
                "direction": "BULLISH_BIAS",
                "interpretation": (
                    "Long positioning is crowded"
                ),
            }

        if value <= 0.67:

            return {
                "status": "SHORT_HEAVY",
                "direction": "BEARISH_BIAS",
                "interpretation": (
                    "Short positioning is crowded"
                ),
            }

        return {
            "status": "BALANCED",
            "direction": "NEUTRAL",
            "interpretation": (
                "Long/short positioning balanced"
            ),
        }

    # ==========================================================
    # Liquidations
    # ==========================================================

    def analyze_liquidations(
        self,
        long_liquidations: Any,
        short_liquidations: Any,
    ) -> Dict[str, Any]:

        long_liq = self._number(
            long_liquidations
        )

        short_liq = self._number(
            short_liquidations
        )

        if (
            long_liq is None
            or short_liq is None
        ):

            return {
                "status": "UNKNOWN",
                "dominant": "UNKNOWN",
                "ratio": None,
                "interpretation": (
                    "Liquidation data unavailable"
                ),
            }

        total = (
            long_liq
            + short_liq
        )

        if total <= 0:

            return {
                "status": "NONE",
                "dominant": "NONE",
                "ratio": None,
                "interpretation": (
                    "No significant liquidation"
                ),
            }

        if long_liq > short_liq:

            dominant = "LONGS"

            ratio = (
                long_liq
                / short_liq
                if short_liq > 0
                else None
            )

        else:

            dominant = "SHORTS"

            ratio = (
                short_liq
                / long_liq
                if long_liq > 0
                else None
            )

        return {
            "status": "ACTIVE",
            "dominant": dominant,
            "ratio": (
                round(ratio, 2)
                if ratio is not None
                else None
            ),
            "long_liquidations": (
                long_liq
            ),
            "short_liquidations": (
                short_liq
            ),
            "interpretation": (
                f"{dominant} experienced "
                "more liquidation"
            ),
        }

    # ==========================================================
    # Full Context
    # ==========================================================

    def analyze(
        self,
        data: Dict[str, Any],
    ) -> Dict[str, Any]:

        oi = self.analyze_open_interest(
            current_oi=data.get(
                "current_oi"
            ),
            previous_oi=data.get(
                "previous_oi"
            ),
            price_change_pct=data.get(
                "price_change_pct"
            ),
        )

        funding = self.analyze_funding(
            data.get(
                "funding_rate"
            )
        )

        long_short = (
            self.analyze_long_short_ratio(
                data.get(
                    "long_short_ratio"
                )
            )
        )

        liquidations = (
            self.analyze_liquidations(
                data.get(
                    "long_liquidations"
                ),
                data.get(
                    "short_liquidations"
                ),
            )
        )

        bullish_score = 0
        bearish_score = 0

        evidence: List[str] = []
        warnings: List[str] = []

        # ------------------------------------------------------
        # OI
        # ------------------------------------------------------

        if (
            oi["status"]
            == "INCREASING"
        ):

            if (
                data.get(
                    "price_change_pct"
                ) is not None
                and float(
                    data[
                        "price_change_pct"
                    ]
                ) > 0
            ):

                bullish_score += 20

                evidence.append(
                    "OI rising with price"
                )

            elif (
                data.get(
                    "price_change_pct"
                ) is not None
                and float(
                    data[
                        "price_change_pct"
                    ]
                ) < 0
            ):

                bearish_score += 20

                evidence.append(
                    "OI rising while price falls"
                )

            else:

                warnings.append(
                    "OI rising without price confirmation"
                )

        elif (
            oi["status"]
            == "DECREASING"
        ):

            warnings.append(
                oi["interpretation"]
            )

        # ------------------------------------------------------
        # Funding
        # ------------------------------------------------------

        if (
            funding["direction"]
            == "BULLISH_BIAS"
        ):

            if funding["risk"] == "HIGH":

                warnings.append(
                    "Crowded long funding"
                )

            else:

                evidence.append(
                    "Moderately positive funding"
                )

        elif (
            funding["direction"]
            == "BEARISH_BIAS"
        ):

            if funding["risk"] == "HIGH":

                warnings.append(
                    "Crowded short funding"
                )

            else:

                evidence.append(
                    "Moderately negative funding"
                )

        # ------------------------------------------------------
        # Long/Short
        # ------------------------------------------------------

        if (
            long_short["status"]
            == "LONG_HEAVY"
        ):

            warnings.append(
                "Long positioning is crowded"
            )

        elif (
            long_short["status"]
            == "SHORT_HEAVY"
        ):

            warnings.append(
                "Short positioning is crowded"
            )

        # ------------------------------------------------------
        # Liquidations
        # ------------------------------------------------------

        if (
            liquidations["status"]
            == "ACTIVE"
        ):

            if (
                liquidations[
                    "dominant"
                ]
                == "LONGS"
            ):

                evidence.append(
                    "Long liquidations detected"
                )

            elif (
                liquidations[
                    "dominant"
                ]
                == "SHORTS"
            ):

                evidence.append(
                    "Short liquidations detected"
                )

        # ------------------------------------------------------
        # Score
        # ------------------------------------------------------

        total = (
            bullish_score
            + bearish_score
        )

        if total > 0:

            if (
                bullish_score
                > bearish_score
            ):

                direction = "BULLISH"

            elif (
                bearish_score
                > bullish_score
            ):

                direction = "BEARISH"

            else:

                direction = "NEUTRAL"

        else:

            direction = "NEUTRAL"

        score = max(
            bullish_score,
            bearish_score,
        )

        return {
            "direction": direction,
            "score": min(
                score,
                100,
            ),
            "bullish_score": (
                bullish_score
            ),
            "bearish_score": (
                bearish_score
            ),
            "open_interest": oi,
            "funding": funding,
            "long_short": long_short,
            "liquidations": liquidations,
            "evidence": evidence,
            "warnings": warnings,
            "status": "SUCCESS",
        }
