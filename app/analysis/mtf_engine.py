import logging
from typing import Any, Dict, Optional

import pandas as pd


logger = logging.getLogger("crypto-signal-bot")


class MultiTimeframeEngine:
    """
    Multi-Timeframe Analysis Engine.

    Timeframes:
        4H  -> Macro trend
        1H  -> Primary setup
        15m -> Tactical setup
        5m  -> Entry timing

    This engine does NOT generate the final trading signal.
    It produces directional alignment and confidence evidence.
    """

    def __init__(self):
        self.weights = {
            "4h": 0.35,
            "1h": 0.30,
            "15m": 0.20,
            "5m": 0.15,
        }

    # ==========================================================
    # Helpers
    # ==========================================================

    @staticmethod
    def _validate_df(
        df: Optional[pd.DataFrame],
    ) -> bool:

        if df is None or df.empty:
            return False

        required = {
            "open",
            "high",
            "low",
            "close",
            "volume",
        }

        return required.issubset(
            df.columns
        )

    # ==========================================================
    # Analyze one timeframe
    # ==========================================================

    def analyze_timeframe(
        self,
        df: pd.DataFrame,
    ) -> Dict[str, Any]:

        if not self._validate_df(df):

            return {
                "direction": "UNKNOWN",
                "score": 0,
                "confidence": 0,
            }

        data = df.copy()

        close = data["close"]

        # ------------------------------------------------------
        # EMA
        # ------------------------------------------------------

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

        # ------------------------------------------------------
        # RSI
        # ------------------------------------------------------

        delta = close.diff()

        gain = (
            delta.clip(lower=0)
            .rolling(14)
            .mean()
        )

        loss = (
            -delta.clip(upper=0)
            .rolling(14)
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

        # ------------------------------------------------------
        # MACD
        # ------------------------------------------------------

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

        signal = (
            macd
            .ewm(
                span=9,
                adjust=False,
            )
            .mean()
        )

        # ------------------------------------------------------
        # Current values
        # ------------------------------------------------------

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

        current_rsi = float(
            rsi.iloc[-1]
        ) if pd.notna(
            rsi.iloc[-1]
        ) else 50.0

        current_macd = float(
            macd.iloc[-1]
        )

        current_signal = float(
            signal.iloc[-1]
        )

        # ======================================================
        # Direction scoring
        # ======================================================

        bullish_points = 0
        bearish_points = 0

        evidence = []

        # EMA20 vs EMA50
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

        # EMA50 vs EMA100
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

        # Price vs EMA20
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

        # RSI
        if current_rsi >= 55:

            bullish_points += 15

            evidence.append(
                f"RSI bullish ({current_rsi:.1f})"
            )

        elif current_rsi <= 45:

            bearish_points += 15

            evidence.append(
                f"RSI bearish ({current_rsi:.1f})"
            )

        else:

            evidence.append(
                f"RSI neutral ({current_rsi:.1f})"
            )

        # MACD
        if current_macd > current_signal:

            bullish_points += 15

            evidence.append(
                "MACD bullish"
            )

        else:

            bearish_points += 15

            evidence.append(
                "MACD bearish"
            )

        # Price momentum
        if len(close) >= 10:

            old_price = float(
                close.iloc[-10]
            )

            if current_close > old_price:

                bullish_points += 20

                evidence.append(
                    "Short-term momentum bullish"
                )

            elif current_close < old_price:

                bearish_points += 20

                evidence.append(
                    "Short-term momentum bearish"
                )

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

        if total_points > 0:

            directional_score = (
                max(
                    bullish_points,
                    bearish_points,
                )
                / total_points
            ) * 100

        else:

            directional_score = 0

        return {
            "direction": direction,
            "score": round(
                directional_score,
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
            "macd_signal": current_signal,
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

        results = {}

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
                result["direction"]
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
        # Direction
        # ------------------------------------------------------

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

        # ------------------------------------------------------
        # Alignment
        # ------------------------------------------------------

        directions = []

        for timeframe in (
            "4h",
            "1h",
            "15m",
            "5m",
        ):

            d = results[
                timeframe
            ]["direction"]

            if d != "UNKNOWN":

                directions.append(d)

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

            alignment = 0

        # ------------------------------------------------------
        # Higher timeframe agreement
        # ------------------------------------------------------

        higher_tf = results["4h"]
        setup_tf = results["1h"]
        tactical_tf = results["15m"]
        entry_tf = results["5m"]

        higher_agreement = 0

        if (
            higher_tf["direction"]
            == direction
        ):

            higher_agreement += 50

        if (
            setup_tf["direction"]
            == direction
        ):

            higher_agreement += 50

        # ------------------------------------------------------
        # Entry timing
        # ------------------------------------------------------

        if (
            entry_tf["direction"]
            == direction
        ):

            entry_timing = "ALIGNED"

        elif (
            entry_tf["direction"]
            == "NEUTRAL"
        ):

            entry_timing = "NEUTRAL"

        else:

            entry_timing = "CONTRARY"

        # ------------------------------------------------------
        # Overall score
        # ------------------------------------------------------

        overall_score = (
            (
                max(
                    bullish_score,
                    bearish_score,
                )
                * 0.55
            )
            + (
                alignment
                * 0.25
            )
            + (
                higher_agreement
                * 0.20
            )
        )

        overall_score = min(
            100,
            max(
                0,
                overall_score,
            ),
        )

        return {
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
            "entry_timing": entry_timing,
            "timeframes": results,
        }
