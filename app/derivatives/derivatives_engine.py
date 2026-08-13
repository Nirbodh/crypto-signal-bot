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

    ✅ FIXED: Funding, Long/Short, Liquidations now contribute to score.
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
            "bullish_score": 0,
            "bearish_score": 0,
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

                result["bullish_score"] = 20
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

                result["bearish_score"] = 20
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

                result["bullish_score"] = 10
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

                result["bearish_score"] = 10
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
                "direction": "NEUTRAL",
                "risk": "UNKNOWN",
                "bullish_score": 0,
                "bearish_score": 0,
                "interpretation": (
                    "Funding data unavailable"
                ),
            }

        # Positive funding:
        # longs pay shorts.

        if funding > self.funding_extreme:

            return {
                "status": "EXTREME",
                "direction": "BEARISH",  # Crowded longs → downside risk
                "risk": "HIGH",
                "bullish_score": 0,
                "bearish_score": 10,     # Contrarian warning
                "interpretation": (
                    "Crowded long positioning - downside risk"
                ),
            }

        if funding > self.funding_neutral:

            return {
                "status": "POSITIVE",
                "direction": "BULLISH",
                "risk": "MODERATE",
                "bullish_score": 15,
                "bearish_score": 0,
                "interpretation": (
                    "Longs dominate funding - bullish bias"
                ),
            }

        # Negative funding:
        # shorts pay longs.

        if funding < -self.funding_extreme:

            return {
                "status": "EXTREME",
                "direction": "BULLISH",  # Crowded shorts → upside risk
                "risk": "HIGH",
                "bullish_score": 10,     # Contrarian warning
                "bearish_score": 0,
                "interpretation": (
                    "Crowded short positioning - upside risk"
                ),
            }

        if funding < -self.funding_neutral:

            return {
                "status": "NEGATIVE",
                "direction": "BEARISH",
                "risk": "MODERATE",
                "bullish_score": 0,
                "bearish_score": 15,
                "interpretation": (
                    "Shorts dominate funding - bearish bias"
                ),
            }

        return {
            "status": "NEUTRAL",
            "direction": "NEUTRAL",
            "risk": "LOW",
            "bullish_score": 0,
            "bearish_score": 0,
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
                "direction": "NEUTRAL",
                "bullish_score": 0,
                "bearish_score": 0,
                "interpretation": (
                    "Long/short ratio unavailable"
                ),
            }

        if value >= 1.5:

            return {
                "status": "LONG_HEAVY",
                "direction": "BEARISH",  # Crowded longs → downside risk
                "bullish_score": 0,
                "bearish_score": 10,
                "interpretation": (
                    "Long positioning is crowded - caution"
                ),
            }

        if value <= 0.67:

            return {
                "status": "SHORT_HEAVY",
                "direction": "BULLISH",  # Crowded shorts → upside risk
                "bullish_score": 10,
                "bearish_score": 0,
                "interpretation": (
                    "Short positioning is crowded - caution"
                ),
            }

        return {
            "status": "BALANCED",
            "direction": "NEUTRAL",
            "bullish_score": 0,
            "bearish_score": 0,
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
        price_change_pct: Any = None,
    ) -> Dict[str, Any]:

        long_liq = self._number(
            long_liquidations
        )

        short_liq = self._number(
            short_liquidations
        )

        price_change = self._number(
            price_change_pct
        )

        if (
            long_liq is None
            or short_liq is None
        ):

            return {
                "status": "UNKNOWN",
                "dominant": "UNKNOWN",
                "bullish_score": 0,
                "bearish_score": 0,
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
                "bullish_score": 0,
                "bearish_score": 0,
                "interpretation": (
                    "No significant liquidation"
                ),
            }

        # ------------------------------------------------------
        # Determine dominant liquidation and score
        # ------------------------------------------------------

        if long_liq > short_liq:
            dominant = "LONGS"
            # Long liquidation usually happens during price drops
            # → bearish context (with price check)
            if price_change is not None and price_change < 0:
                # Price fell → long liquidation confirms bearish pressure
                return {
                    "status": "ACTIVE",
                    "dominant": dominant,
                    "bullish_score": 0,
                    "bearish_score": 15,
                    "interpretation": (
                        "Long liquidations during price drop - bearish"
                    ),
                }
            else:
                # Long liquidation without clear price drop
                return {
                    "status": "ACTIVE",
                    "dominant": dominant,
                    "bullish_score": 0,
                    "bearish_score": 5,
                    "interpretation": (
                        "Long liquidations detected - caution"
                    ),
                }
        else:
            dominant = "SHORTS"
            # Short liquidation usually happens during price rises
            # → bullish context (with price check)
            if price_change is not None and price_change > 0:
                return {
                    "status": "ACTIVE",
                    "dominant": dominant,
                    "bullish_score": 15,
                    "bearish_score": 0,
                    "interpretation": (
                        "Short liquidations during price rise - bullish"
                    ),
                }
            else:
                return {
                    "status": "ACTIVE",
                    "dominant": dominant,
                    "bullish_score": 5,
                    "bearish_score": 0,
                    "interpretation": (
                        "Short liquidations detected - caution"
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
                data.get(
                    "price_change_pct"
                ),
            )
        )

        # ==========================================================
        # 🔥 NEW: Aggregate scores from all components
        # ==========================================================

        bullish_score = 0
        bearish_score = 0

        evidence: List[str] = []
        warnings: List[str] = []

        # ------------------------------------------------------
        # OI
        # ------------------------------------------------------

        bullish_score += oi.get("bullish_score", 0)
        bearish_score += oi.get("bearish_score", 0)

        if oi.get("bullish_score", 0) > 0:
            evidence.append("OI supporting bullish")
        elif oi.get("bearish_score", 0) > 0:
            evidence.append("OI supporting bearish")

        if oi["status"] == "INCREASING" and oi.get("bullish_score") == 0 and oi.get("bearish_score") == 0:
            warnings.append("OI rising without price confirmation")

        # ------------------------------------------------------
        # Funding
        # ------------------------------------------------------

        bullish_score += funding.get("bullish_score", 0)
        bearish_score += funding.get("bearish_score", 0)

        if funding.get("bullish_score", 0) > 0:
            evidence.append("Positive funding bias")
        elif funding.get("bearish_score", 0) > 0:
            evidence.append("Negative funding bias")

        if funding["risk"] == "HIGH":
            warnings.append("Extreme funding - crowded positioning")

        # ------------------------------------------------------
        # Long/Short
        # ------------------------------------------------------

        bullish_score += long_short.get("bullish_score", 0)
        bearish_score += long_short.get("bearish_score", 0)

        if long_short.get("bullish_score", 0) > 0:
            evidence.append("Short positioning crowded - potential squeeze")
        elif long_short.get("bearish_score", 0) > 0:
            evidence.append("Long positioning crowded - caution")

        # ------------------------------------------------------
        # Liquidations
        # ------------------------------------------------------

        bullish_score += liquidations.get("bullish_score", 0)
        bearish_score += liquidations.get("bearish_score", 0)

        if liquidations.get("bullish_score", 0) > 0:
            evidence.append("Short liquidations detected")
        elif liquidations.get("bearish_score", 0) > 0:
            evidence.append("Long liquidations detected")

        # ------------------------------------------------------
        # Final Direction & Score
        # ------------------------------------------------------

        if bullish_score > bearish_score:
            direction = "BULLISH"
        elif bearish_score > bullish_score:
            direction = "BEARISH"
        else:
            direction = "NEUTRAL"

        score = max(bullish_score, bearish_score)

        # Cap at 100
        score = min(score, 100)

        return {
            "direction": direction,
            "score": round(score, 2),
            "bullish_score": round(bullish_score, 2),
            "bearish_score": round(bearish_score, 2),
            "open_interest": oi,
            "funding": funding,
            "long_short": long_short,
            "liquidations": liquidations,
            "evidence": evidence,
            "warnings": warnings,
            "status": "SUCCESS",
        }
