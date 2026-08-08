import logging
from typing import Any, Dict, Optional

import pandas as pd


logger = logging.getLogger("crypto-signal-bot")


class MultiTimeframeEngine:
    """
    Production Multi-Timeframe Analysis Engine.

    Required timeframes:
        4h  -> Macro trend
        1h  -> Primary setup
        15m -> Tactical setup
        5m  -> Entry timing

    IMPORTANT
    ---------
    This engine requires REAL OHLCV data.

    Expected input:

        {
            "4h": DataFrame,
            "1h": DataFrame,
            "15m": DataFrame,
            "5m": DataFrame,
        }

    Missing timeframe data is marked UNKNOWN.

    No fake/default market data is created.
    """

    TIMEFRAMES = (
        "4h",
        "1h",
        "15m",
        "5m",
    )

    def __init__(self):

        self.weights = {
            "4h": 0.35,
            "1h": 0.30,
            "15m": 0.20,
            "5m": 0.15,
        }

        self.required_candles = 120

    # ==========================================================
    # Validation
    # ==========================================================

    @staticmethod
    def _validate_df(
        df: Optional[pd.DataFrame],
        minimum_candles: int = 120,
    ) -> bool:

        if df is None:
            return False

        if not isinstance(
            df,
            pd.DataFrame,
        ):
            return False

        if df.empty:
            return False

        required = {
            "open",
            "high",
            "low",
            "close",
            "volume",
        }

        if not required.issubset(
            df.columns
        ):
            return False

        if len(df) < minimum_candles:
            return False

        return True

    # ==========================================================
    # Unknown Result
    # ==========================================================

    @staticmethod
    def _unknown_result(
        reason: str,
    ) -> Dict[str, Any]:

        return {
            "status": "UNAVAILABLE",
            "direction": "UNKNOWN",
            "score": None,
            "confidence": 0.0,
            "bullish_points": 0,
            "bearish_points": 0,
            "evidence": [],
            "reason": reason,
        }

    # ==========================================================
    # Analyze One Timeframe
    # ==========================================================

    def analyze_timeframe(
        self,
        df: Optional[pd.DataFrame],
    ) -> Dict[str, Any]:

        if not self._validate_df(
            df,
            self.required_candles,
        ):

            return self._unknown_result(
                "INVALID_OR_INSUFFICIENT_OHLCV"
            )

        data = df.copy()

        # ------------------------------------------------------
        # Numeric cleanup
        # ------------------------------------------------------

        for column in (
            "open",
            "high",
            "low",
            "close",
            "volume",
        ):

            data[column] = pd.to_numeric(
                data[column],
                errors="coerce",
            )

        data = data.dropna(
            subset=[
                "open",
                "high",
                "low",
                "close",
                "volume",
            ]
        )

        if len(data) < self.required_candles:

            return self._unknown_result(
                "INSUFFICIENT_VALID_CANDLES"
            )

        close = data["close"]

        # ======================================================
        # EMA
        # ======================================================

        ema20 = close.ewm(
            span=20,
            adjust=False,
        ).mean()

        ema50 = close.ewm(
            span=50,
            adjust=False,
        ).mean()

        ema100 = close.ewm(
            span=100,
            adjust=False,
        ).mean()

        # ======================================================
        # RSI
        # ======================================================

        delta = close.diff()

        gain = (
            delta
            .clip(lower=0)
            .rolling(
                14,
                min_periods=14,
            )
            .mean()
        )

        loss = (
            -delta
            .clip(upper=0)
            .rolling(
                14,
                min_periods=14,
            )
            .mean()
        )

        rs = gain / loss.replace(
            0,
            pd.NA,
        )

        rsi = (
            100
            - (
                100
                / (1 + rs)
            )
        )

        # ======================================================
        # MACD
        # ======================================================

        ema12 = close.ewm(
            span=12,
            adjust=False,
        ).mean()

        ema26 = close.ewm(
            span=26,
            adjust=False,
        ).mean()

        macd = ema12 - ema26

        macd_signal = macd.ewm(
            span=9,
            adjust=False,
        ).mean()

        # ======================================================
        # Current values
        # ======================================================

        current_close = float(
            close.iloc[-1]
        )

        current_ema20 = float(
            ema20.iloc[-1]
        )

        current_ema50 = float(
            ema50.iloc[-1]
        )

        current_ema100 = float(
            ema100.iloc[-1]
        )

        current_rsi = (
            float(rsi.iloc[-1])
            if pd.notna(rsi.iloc[-1])
            else None
        )

        current_macd = float(
            macd.iloc[-1]
        )

        current_macd_signal = float(
            macd_signal.iloc[-1]
        )

        if current_rsi is None:

            return self._unknown_result(
                "RSI_UNAVAILABLE"
            )

        # ======================================================
        # Scoring
        # ======================================================

        bullish_points = 0
        bearish_points = 0

        evidence = []

        # ------------------------------------------------------
        # EMA20 / EMA50
        # ------------------------------------------------------

        if current_ema20 > current_ema50:

            bullish_points += 20

            evidence.append(
                "EMA20 above EMA50"
            )

        elif current_ema20 < current_ema50:

            bearish_points += 20

            evidence.append(
                "EMA20 below EMA50"
            )

        # ------------------------------------------------------
        # EMA50 / EMA100
        # ------------------------------------------------------

        if current_ema50 > current_ema100:

            bullish_points += 15

            evidence.append(
                "EMA50 above EMA100"
            )

        elif current_ema50 < current_ema100:

            bearish_points += 15

            evidence.append(
                "EMA50 below EMA100"
            )

        # ------------------------------------------------------
        # Price / EMA20
        # ------------------------------------------------------

        if current_close > current_ema20:

            bullish_points += 15

            evidence.append(
                "Price above EMA20"
            )

        elif current_close < current_ema20:

            bearish_points += 15

            evidence.append(
                "Price below EMA20"
            )

        # ------------------------------------------------------
        # RSI
        # ------------------------------------------------------

        if 55 <= current_rsi < 70:

            bullish_points += 15

            evidence.append(
                f"RSI bullish ({current_rsi:.1f})"
            )

        elif 70 <= current_rsi < 80:

            bullish_points += 5

            evidence.append(
                f"RSI elevated / late ({current_rsi:.1f})"
            )

        elif current_rsi >= 80:

            bearish_points += 5

            evidence.append(
                f"RSI extreme overbought ({current_rsi:.1f})"
            )

        elif 30 < current_rsi <= 45:

            bearish_points += 15

            evidence.append(
                f"RSI bearish ({current_rsi:.1f})"
            )

        elif current_rsi <= 30:

            bearish_points += 5

            evidence.append(
                f"RSI extreme oversold ({current_rsi:.1f})"
            )

        else:

            evidence.append(
                f"RSI neutral ({current_rsi:.1f})"
            )

        # ------------------------------------------------------
        # MACD
        # ------------------------------------------------------

        if current_macd > current_macd_signal:

            bullish_points += 15

            evidence.append(
                "MACD bullish"
            )

        elif current_macd < current_macd_signal:

            bearish_points += 15

            evidence.append(
                "MACD bearish"
            )

        # ------------------------------------------------------
        # Momentum
        # ------------------------------------------------------

        momentum_points = 10

        if len(close) >= 11:

            old_price = float(
                close.iloc[-11]
            )

            if old_price > 0:

                momentum_pct = (
                    (
                        current_close
                        - old_price
                    )
                    / old_price
                ) * 100.0

                if momentum_pct > 0:

                    bullish_points += momentum_points

                    evidence.append(
                        f"Short-term momentum bullish "
                        f"({momentum_pct:.2f}%)"
                    )

                elif momentum_pct < 0:

                    bearish_points += momentum_points

                    evidence.append(
                        f"Short-term momentum bearish "
                        f"({momentum_pct:.2f}%)"
                    )

                else:

                    evidence.append(
                        "Short-term momentum neutral"
                    )

        # ======================================================
        # Direction
        # ======================================================

        total_points = (
            bullish_points
            + bearish_points
        )

        if bullish_points > bearish_points:

            direction = "BULLISH"

        elif bearish_points > bullish_points:

            direction = "BEARISH"

        else:

            direction = "NEUTRAL"

        # ------------------------------------------------------
        # Directional score
        # ------------------------------------------------------

        if total_points > 0:

            directional_score = (
                max(
                    bullish_points,
                    bearish_points,
                )
                / total_points
            ) * 100.0

        else:

            directional_score = 0.0

        # ------------------------------------------------------
        # Confidence
        # ------------------------------------------------------

        if total_points > 0:

            confidence = (
                abs(
                    bullish_points
                    - bearish_points
                )
                / total_points
            ) * 100.0

        else:

            confidence = 0.0

        return {
            "status": "SUCCESS",
            "direction": direction,
            "score": round(
                directional_score,
                2,
            ),
            "confidence": round(
                confidence,
                2,
            ),
            "bullish_points": bullish_points,
            "bearish_points": bearish_points,
            "rsi": round(
                current_rsi,
                2,
            ),
            "ema20": current_ema20,
            "ema50": current_ema50,
            "ema100": current_ema100,
            "macd": current_macd,
            "macd_signal": current_macd_signal,
            "evidence": evidence,
        }

    # ==========================================================
    # Evaluate All Timeframes
    # ==========================================================

    def evaluate(
        self,
        timeframe_data: Dict[
            str,
            pd.DataFrame,
        ],
    ) -> Dict[str, Any]:

        if not isinstance(
            timeframe_data,
            dict,
        ):

            return {
                "status": "ERROR",
                "direction": "UNKNOWN",
                "score": None,
                "confidence": 0.0,
                "reason": (
                    "timeframe_data must be a dictionary"
                ),
            }

        results = {}

        # ------------------------------------------------------
        # Analyze each timeframe
        # ------------------------------------------------------

        for timeframe in self.TIMEFRAMES:

            results[timeframe] = (
                self.analyze_timeframe(
                    timeframe_data.get(
                        timeframe
                    )
                )
            )

        # ------------------------------------------------------
        # Weighted directional scores
        # ------------------------------------------------------

        bullish_score = 0.0
        bearish_score = 0.0
        valid_weight = 0.0

        for timeframe, weight in self.weights.items():

            result = results[timeframe]

            direction = result.get(
                "direction"
            )

            score = result.get(
                "score"
            )

            if direction == "UNKNOWN":
                continue

            if score is None:
                continue

            valid_weight += weight

            if direction == "BULLISH":

                bullish_score += (
                    score * weight
                )

            elif direction == "BEARISH":

                bearish_score += (
                    score * weight
                )

        if valid_weight > 0:

            bullish_score /= valid_weight
            bearish_score /= valid_weight

        # ------------------------------------------------------
        # Direction
        # ------------------------------------------------------

        if bullish_score > bearish_score:

            direction = "BULLISH"

        elif bearish_score > bullish_score:

            direction = "BEARISH"

        else:

            direction = "NEUTRAL"

        # ------------------------------------------------------
        # Alignment
        #
        # UNKNOWN is excluded.
        # NEUTRAL does not count as bullish/bearish agreement.
        # ------------------------------------------------------

        valid_direction_results = [
            result
            for result in results.values()
            if result.get("direction")
            in {
                "BULLISH",
                "BEARISH",
            }
        ]

        if valid_direction_results:

            aligned_count = sum(
                1
                for result
                in valid_direction_results
                if result.get("direction")
                == direction
            )

            alignment = (
                aligned_count
                / len(valid_direction_results)
            ) * 100.0

        else:

            alignment = 0.0

        # ------------------------------------------------------
        # Higher timeframe agreement
        # ------------------------------------------------------

        higher_agreement = 0

        if (
            direction != "NEUTRAL"
            and results["4h"].get("direction")
            == direction
        ):

            higher_agreement += 50

        if (
            direction != "NEUTRAL"
            and results["1h"].get("direction")
            == direction
        ):

            higher_agreement += 50

        # ------------------------------------------------------
        # Tactical agreement
        # ------------------------------------------------------

        tactical_agreement = 0

        if (
            direction != "NEUTRAL"
            and results["15m"].get("direction")
            == direction
        ):

            tactical_agreement = 100

        # ------------------------------------------------------
        # Entry timing
        # ------------------------------------------------------

        entry_direction = results["5m"].get(
            "direction"
        )

        if (
            direction != "NEUTRAL"
            and entry_direction == direction
        ):

            entry_timing = "ALIGNED"

        elif entry_direction == "NEUTRAL":

            entry_timing = "NEUTRAL"

        elif entry_direction == "UNKNOWN":

            entry_timing = "UNAVAILABLE"

        else:

            entry_timing = "CONTRARY"

        # ------------------------------------------------------
        # Overall score
        # ------------------------------------------------------

        if valid_weight <= 0:

            overall_score = None

        else:

            directional_component = max(
                bullish_score,
                bearish_score,
            )

            overall_score = (
                directional_component * 0.55
                + alignment * 0.20
                + higher_agreement * 0.15
                + tactical_agreement * 0.10
            )

            if entry_timing == "CONTRARY":

                overall_score *= 0.90

            elif entry_timing == "UNAVAILABLE":

                overall_score *= 0.95

            overall_score = min(
                100.0,
                max(
                    0.0,
                    overall_score,
                ),
            )

        # ------------------------------------------------------
        # Valid timeframe count
        # ------------------------------------------------------

        valid_timeframes = sum(
            1
            for result in results.values()
            if result.get("direction")
            != "UNKNOWN"
        )

        missing_timeframes = [
            timeframe
            for timeframe, result
            in results.items()
            if result.get("direction")
            == "UNKNOWN"
        ]

        if valid_timeframes == 0:

            status = "UNAVAILABLE"

        elif valid_timeframes < 4:

            status = "PARTIAL"

        else:

            status = "SUCCESS"

        # ------------------------------------------------------
        # Confidence
        # ------------------------------------------------------

        if direction == "NEUTRAL":

            confidence = 0.0

        else:

            directional_total = (
                bullish_score
                + bearish_score
            )

            if directional_total > 0:

                directional_confidence = (
                    abs(
                        bullish_score
                        - bearish_score
                    )
                    / directional_total
                ) * 100.0

            else:

                directional_confidence = 0.0

            confidence = (
                directional_confidence * 0.60
                + alignment * 0.40
            )

            confidence = min(
                100.0,
                max(
                    0.0,
                    confidence,
                ),
            )

        return {
            "status": status,
            "direction": direction,
            "score": (
                round(
                    overall_score,
                    2,
                )
                if overall_score is not None
                else None
            ),
            "confidence": round(
                confidence,
                2,
            ),
            "bullish_score": round(
                bullish_score,
                2,
            ),
            "bearish_score": round(
                bearish_score,
                2,
            ),
            "alignment": round(
                alignment,
                2,
            ),
            "higher_tf_agreement": higher_agreement,
            "tactical_agreement": tactical_agreement,
            "entry_timing": entry_timing,
            "valid_timeframes": valid_timeframes,
            "missing_timeframes": missing_timeframes,
            "timeframes": results,
        }
