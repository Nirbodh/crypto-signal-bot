import logging
from typing import Any, Dict, Optional

import pandas as pd


logger = logging.getLogger("crypto-signal-bot")


class MultiTimeframeEngine:
    """
    Production Multi-Timeframe Analysis Engine.

    Timeframes:
        4H  -> Macro trend
        1H  -> Primary setup
        15m -> Tactical setup
        5m  -> Entry timing

    This engine does NOT generate the final trading signal.

    It evaluates:
        - EMA structure
        - RSI
        - MACD
        - Momentum
        - Directional alignment
        - Higher timeframe agreement
        - Entry timing

    IMPORTANT:
        This engine requires REAL OHLCV data for each timeframe.

        Expected input:

        {
            "4h": DataFrame,
            "1h": DataFrame,
            "15m": DataFrame,
            "5m": DataFrame
        }

        Missing timeframe data is marked UNKNOWN.
        No fake/default market data is created.
    """

    # ==========================================================
    # Initialization
    # ==========================================================

    def __init__(self):

        self.weights = {
            "4h": 0.35,
            "1h": 0.30,
            "15m": 0.20,
            "5m": 0.15,
        }

        self.required_candles = 120

    # ==========================================================
    # Helpers
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

    @staticmethod
    def _unknown_result(
        reason: str,
    ) -> Dict[str, Any]:

        return {
            "status": "UNAVAILABLE",
            "direction": "UNKNOWN",
            "score": 0.0,
            "confidence": 0.0,
            "bullish_points": 0,
            "bearish_points": 0,
            "evidence": [],
            "reason": reason,
        }

    # ==========================================================
    # Analyze one timeframe
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

        ema20 = (
            close
            .ewm(
                span=20,
                adjust=False,
            )
            .mean()
        )

        ema50 = (
            close
            .ewm(
                span=50,
                adjust=False,
            )
            .mean()
        )

        ema100 = (
            close
            .ewm(
                span=100,
                adjust=False,
            )
            .mean()
        )

        # ======================================================
        # RSI
        # ======================================================

        delta = close.diff()

        gain = (
            delta.clip(lower=0)
            .rolling(
                14,
                min_periods=14,
            )
            .mean()
        )

        loss = (
            -delta.clip(upper=0)
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

        ema12 = (
            close
            .ewm(
                span=12,
                adjust=False,
            )
            .mean()
        )

        ema26 = (
            close
            .ewm(
                span=26,
                adjust=False,
            )
            .mean()
        )

        macd = ema12 - ema26

        macd_signal = (
            macd
            .ewm(
                span=9,
                adjust=False,
            )
            .mean()
        )

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
            if pd.notna(
                rsi.iloc[-1]
            )
            else 50.0
        )

        current_macd = float(
            macd.iloc[-1]
        )

        current_macd_signal = float(
            macd_signal.iloc[-1]
        )

        # ======================================================
        # Scoring
        # ======================================================

        bullish_points = 0
        bearish_points = 0

        evidence = []

        # ------------------------------------------------------
        # 1. EMA20 vs EMA50
        # ------------------------------------------------------

        if current_ema20 > current_ema50:

            bullish_points += 20

            evidence.append(
                "EMA20 above EMA50"
            )

        else:

            bearish_points += 20

            evidence.append(
                "EMA20 below EMA50"
            )

        # ------------------------------------------------------
        # 2. EMA50 vs EMA100
        # ------------------------------------------------------

        if current_ema50 > current_ema100:

            bullish_points += 15

            evidence.append(
                "EMA50 above EMA100"
            )

        else:

            bearish_points += 15

            evidence.append(
                "EMA50 below EMA100"
            )

        # ------------------------------------------------------
        # 3. Price vs EMA20
        # ------------------------------------------------------

        if current_close > current_ema20:

            bullish_points += 15

            evidence.append(
                "Price above EMA20"
            )

        else:

            bearish_points += 15

            evidence.append(
                "Price below EMA20"
            )

        # ------------------------------------------------------
        # 4. RSI
        #
        # IMPORTANT:
        # Extremely high RSI is NOT treated as unlimited
        # bullish confirmation.
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
        # 5. MACD
        # ------------------------------------------------------

        if current_macd > current_macd_signal:

            bullish_points += 15

            evidence.append(
                "MACD bullish"
            )

        else:

            bearish_points += 15

            evidence.append(
                "MACD bearish"
            )

        # ------------------------------------------------------
        # 6. Momentum
        #
        # Reduced from 20 to 10 to avoid allowing short-term
        # noise to dominate the entire timeframe.
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
                ) * 100

            else:

                momentum_pct = 0.0

            if momentum_pct > 0:

                bullish_points += (
                    momentum_points
                )

                evidence.append(
                    "Short-term momentum bullish"
                )

            elif momentum_pct < 0:

                bearish_points += (
                    momentum_points
                )

                evidence.append(
                    "Short-term momentum bearish"
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

        if (
            bullish_points
            > bearish_points
        ):

            direction = "BULLISH"

        elif (
            bearish_points
            > bullish_points
        ):

            direction = "BEARISH"

        else:

            direction = "NEUTRAL"

        if total_points > 0:

            directional_score = (
                max(
                    bullish_points,
                    bearish_points,
                )
                / total_points
            ) * 100

        else:

            directional_score = 0.0

        # ------------------------------------------------------
        # Confidence
        #
        # Directional dominance converted into confidence.
        # ------------------------------------------------------

        if total_points > 0:

            dominance = abs(
                bullish_points
                - bearish_points
            ) / total_points

            confidence = dominance * 100

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
            "bullish_points": (
                bullish_points
            ),
            "bearish_points": (
                bearish_points
            ),
            "rsi": round(
                current_rsi,
                2,
            ),
            "ema20": current_ema20,
            "ema50": current_ema50,
            "ema100": current_ema100,
            "macd": current_macd,
            "macd_signal": (
                current_macd_signal
            ),
            "evidence": evidence,
        }

    # ==========================================================
    # Multi-Timeframe Evaluation
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
                "score": 0.0,
                "reason": (
                    "timeframe_data must be a dictionary"
                ),
            }

        results: Dict[
            str,
            Dict[str, Any],
        ] = {}

        # ------------------------------------------------------
        # Analyze all timeframes
        # ------------------------------------------------------

        for timeframe in (
            "4h",
            "1h",
            "15m",
            "5m",
        ):

            df = timeframe_data.get(
                timeframe
            )

            results[timeframe] = (
                self.analyze_timeframe(df)
            )

        # ------------------------------------------------------
        # Weighted directional score
        # ------------------------------------------------------

        bullish_score = 0.0
        bearish_score = 0.0

        valid_weight = 0.0

        for timeframe, weight in (
            self.weights.items()
        ):

            result = results[
                timeframe
            ]

            if (
                result.get("direction")
                == "UNKNOWN"
            ):
                continue

            valid_weight += weight

            if (
                result["direction"]
                == "BULLISH"
            ):

                bullish_score += (
                    result["score"]
                    * weight
                )

            elif (
                result["direction"]
                == "BEARISH"
            ):

                bearish_score += (
                    result["score"]
                    * weight
                )

        if valid_weight > 0:

            bullish_score /= valid_weight
            bearish_score /= valid_weight

        # ------------------------------------------------------
        # Overall direction
        # ------------------------------------------------------

        if bullish_score > bearish_score:

            direction = "BULLISH"

        elif bearish_score > bullish_score:

            direction = "BEARISH"

        else:

            direction = "NEUTRAL"

        # ------------------------------------------------------
        # Direction alignment
        # ------------------------------------------------------

        directions = []

        for timeframe in (
            "4h",
            "1h",
            "15m",
            "5m",
        ):

            timeframe_direction = results[
                timeframe
            ].get(
                "direction"
            )

            if timeframe_direction in {
                "BULLISH",
                "BEARISH",
                "NEUTRAL",
            }:

                directions.append(
                    timeframe_direction
                )

        if directions:

            bullish_count = directions.count(
                "BULLISH"
            )

            bearish_count = directions.count(
                "BEARISH"
            )

            neutral_count = directions.count(
                "NEUTRAL"
            )

            max_count = max(
                bullish_count,
                bearish_count,
                neutral_count,
            )

            alignment = (
                max_count
                / len(directions)
            ) * 100

        else:

            alignment = 0.0

        # ------------------------------------------------------
        # Higher timeframe agreement
        # ------------------------------------------------------

        higher_tf = results["4h"]
        setup_tf = results["1h"]
        tactical_tf = results["15m"]
        entry_tf = results["5m"]

        higher_agreement = 0

        if (
            higher_tf.get("direction")
            == direction
        ):

            higher_agreement += 50

        if (
            setup_tf.get("direction")
            == direction
        ):

            higher_agreement += 50

        # ------------------------------------------------------
        # Tactical agreement
        # ------------------------------------------------------

        tactical_agreement = 0

        if (
            tactical_tf.get("direction")
            == direction
        ):

            tactical_agreement = 100

        # ------------------------------------------------------
        # Entry timing
        # ------------------------------------------------------

        if (
            entry_tf.get("direction")
            == direction
        ):

            entry_timing = "ALIGNED"

        elif (
            entry_tf.get("direction")
            == "NEUTRAL"
        ):

            entry_timing = "NEUTRAL"

        elif (
            entry_tf.get("direction")
            == "UNKNOWN"
        ):

            entry_timing = "UNAVAILABLE"

        else:

            entry_timing = "CONTRARY"

        # ------------------------------------------------------
        # Overall score
        #
        # Macro + setup are more important than entry timing.
        # ------------------------------------------------------

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

        # ------------------------------------------------------
        # Entry penalty
        #
        # A contrary 5m does not automatically reject the setup,
        # but it lowers confidence because entry timing is poor.
        # ------------------------------------------------------

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
            if result.get(
                "direction"
            )
            != "UNKNOWN"
        )

        if valid_timeframes == 0:

            status = "UNAVAILABLE"

        elif valid_timeframes < 4:

            status = "PARTIAL"

        else:

            status = "SUCCESS"

        # ------------------------------------------------------
        # Final result
        # ------------------------------------------------------

        return {
            "status": status,
            "direction": direction,
            "score": round(
                overall_score,
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
            "higher_tf_agreement": (
                higher_agreement
            ),
            "tactical_agreement": (
                tactical_agreement
            ),
            "entry_timing": entry_timing,
            "valid_timeframes": (
                valid_timeframes
            ),
            "timeframes": results,
        }
