import logging
from typing import Dict, Optional

import numpy as np
import pandas as pd
from ta.momentum import RSIIndicator
from ta.trend import (
    ADXIndicator,
    EMAIndicator,
    MACD,
)
from ta.volatility import AverageTrueRange
from ta.volume import (
    OnBalanceVolumeIndicator,
    VolumeWeightedAveragePrice,
)


logger = logging.getLogger("crypto-signal-bot")


class TechnicalEngine:
    """
    Technical analysis engine.

    Important:
    This engine does NOT generate BUY/SELL signals.

    It produces structured market evidence that will later
    be combined with SMC, liquidity, derivatives and risk.
    """

    def analyze(
        self,
        df: pd.DataFrame,
    ) -> Optional[Dict]:

        if df is None or df.empty:
            logger.warning("⚠️ DataFrame is None or empty")
            return None

        required_columns = {
            "open",
            "high",
            "low",
            "close",
            "volume",
        }

        if not required_columns.issubset(
            df.columns
        ):
            logger.error(
                "❌ Missing OHLCV columns. Required: %s, Available: %s",
                required_columns,
                list(df.columns)
            )
            return None

        # ==================================================
        # Input validation and cleaning
        # ==================================================

        data = df.copy()

        # Convert to numeric and handle invalid values
        numeric_columns = [
            "open",
            "high",
            "low",
            "close",
            "volume",
        ]

        for column in numeric_columns:
            data[column] = pd.to_numeric(
                data[column],
                errors="coerce",
            )

        # Remove rows with invalid OHLCV values
        data = data.replace(
            [np.inf, -np.inf],
            np.nan,
        )

        data = data.dropna(
            subset=numeric_columns
        ).reset_index(drop=True)

        # Minimum candle requirement (200+ recommended for EMA200)
        MIN_CANDLES = 200
        if len(data) < MIN_CANDLES:
            logger.warning(
                "⚠️ Not enough valid OHLCV candles: %s (need at least %s)",
                len(data),
                MIN_CANDLES
            )
            return None

        # ==================================================
        # EMA
        # ==================================================

        data["ema20"] = EMAIndicator(
            close=data["close"],
            window=20,
        ).ema_indicator()

        data["ema50"] = EMAIndicator(
            close=data["close"],
            window=50,
        ).ema_indicator()

        data["ema200"] = EMAIndicator(
            close=data["close"],
            window=200,
        ).ema_indicator()

        # ==================================================
        # RSI
        # ==================================================

        data["rsi"] = RSIIndicator(
            close=data["close"],
            window=14,
        ).rsi()

        # ==================================================
        # MACD
        # ==================================================

        macd = MACD(
            close=data["close"],
            window_slow=26,
            window_fast=12,
            window_sign=9,
        )

        data["macd"] = macd.macd()
        data["macd_signal"] = (
            macd.macd_signal()
        )
        data["macd_histogram"] = (
            macd.macd_diff()
        )

        # ==================================================
        # ADX
        # ==================================================

        adx = ADXIndicator(
            high=data["high"],
            low=data["low"],
            close=data["close"],
            window=14,
        )

        data["adx"] = adx.adx()
        data["di_plus"] = adx.adx_pos()
        data["di_minus"] = adx.adx_neg()

        # ==================================================
        # ATR
        # ==================================================

        atr = AverageTrueRange(
            high=data["high"],
            low=data["low"],
            close=data["close"],
            window=14,
        )

        data["atr"] = atr.average_true_range()

        # ==================================================
        # OBV
        # ==================================================

        obv = OnBalanceVolumeIndicator(
            close=data["close"],
            volume=data["volume"],
        )

        data["obv"] = obv.on_balance_volume()

        # ==================================================
        # VWAP
        # ==================================================

        vwap = VolumeWeightedAveragePrice(
            high=data["high"],
            low=data["low"],
            close=data["close"],
            volume=data["volume"],
            window=14,
        )

        data["vwap"] = (
            vwap.volume_weighted_average_price()
        )

        # ==================================================
        # Volume analysis
        # ==================================================

        data["volume_sma20"] = (
            data["volume"]
            .rolling(20)
            .mean()
        )

        data["volume_ratio"] = (
            data["volume"]
            / data["volume_sma20"]
        )

        # ==================================================
        # Recent support/resistance
        # ==================================================

        data["recent_support"] = (
            data["low"]
            .rolling(50)
            .min()
        )

        data["recent_resistance"] = (
            data["high"]
            .rolling(50)
            .max()
        )

        # ==================================================
        # Clean infinite and NaN values
        # ==================================================

        data = data.replace(
            [np.inf, -np.inf],
            np.nan,
        )

        # Only drop rows where critical analysis columns are NaN
        critical_columns = [
            "close",
            "ema20",
            "ema50",
            "ema200",
            "rsi",
            "macd",
            "macd_signal",
            "macd_histogram",
            "adx",
            "di_plus",
            "di_minus",
            "atr",
            "obv",
            "vwap",
            "volume_ratio",
            "recent_support",
            "recent_resistance",
        ]

        data = data.dropna(
            subset=critical_columns
        ).reset_index(drop=True)

        # ==================================================
        # ✅ FIX: Ensure at least 2 rows for comparison
        # ==================================================

        MIN_ROWS_FOR_COMPARISON = 2
        if len(data) < MIN_ROWS_FOR_COMPARISON:
            logger.warning(
                "⚠️ Insufficient valid rows after indicator calculation: %s (need at least %s)",
                len(data),
                MIN_ROWS_FOR_COMPARISON
            )
            return None

        latest = data.iloc[-1]
        previous = data.iloc[-2]

        close = float(latest["close"])

        # ==================================================
        # Trend classification
        # ==================================================

        ema20 = float(latest["ema20"])
        ema50 = float(latest["ema50"])
        ema200 = float(latest["ema200"])

        if (
            ema20 > ema50
            and ema50 > ema200
        ):
            trend = "BULLISH"

        elif (
            ema20 < ema50
            and ema50 < ema200
        ):
            trend = "BEARISH"

        else:
            trend = "MIXED"

        # ==================================================
        # MACD state
        # ==================================================

        macd_value = float(
            latest["macd"]
        )

        macd_signal = float(
            latest["macd_signal"]
        )

        previous_macd = float(
            previous["macd"]
        )

        previous_signal = float(
            previous["macd_signal"]
        )

        if (
            macd_value > macd_signal
            and previous_macd
            <= previous_signal
        ):
            macd_state = "BULLISH_CROSS"

        elif (
            macd_value < macd_signal
            and previous_macd
            >= previous_signal
        ):
            macd_state = "BEARISH_CROSS"

        elif macd_value > macd_signal:
            macd_state = "BULLISH"

        else:
            macd_state = "BEARISH"

        # ==================================================
        # RSI state
        # ==================================================

        rsi = float(latest["rsi"])

        if rsi < 30:
            rsi_state = "EXTREME_OVERSOLD"

        elif rsi < 40:
            rsi_state = "OVERSOLD"

        elif rsi < 55:
            rsi_state = "RECOVERY_ZONE"

        elif rsi <= 70:
            rsi_state = "MOMENTUM"

        else:
            rsi_state = "OVERBOUGHT"

        # ==================================================
        # ADX state
        # ==================================================

        adx_value = float(
            latest["adx"]
        )

        if adx_value >= 25:
            adx_state = "STRONG_TREND"

        elif adx_value >= 18:
            adx_state = "DEVELOPING_TREND"

        else:
            adx_state = "WEAK_TREND"

        # ==================================================
        # Volume state
        # ==================================================

        volume_ratio = float(
            latest["volume_ratio"]
        )

        if volume_ratio >= 3:
            volume_state = "EXTREME_SPIKE"

        elif volume_ratio >= 2:
            volume_state = "STRONG_SPIKE"

        elif volume_ratio >= 1.3:
            volume_state = "ELEVATED"

        elif volume_ratio >= 0.8:
            volume_state = "NORMAL"

        else:
            volume_state = "LOW"

        # ==================================================
        # OBV direction
        # ==================================================

        obv_current = float(
            latest["obv"]
        )

        obv_previous = float(
            previous["obv"]
        )

        if obv_current > obv_previous:
            obv_state = "RISING"

        elif obv_current < obv_previous:
            obv_state = "FALLING"

        else:
            obv_state = "FLAT"

        # ==================================================
        # VWAP position
        # ==================================================

        vwap_value = float(
            latest["vwap"]
        )

        if close > vwap_value:
            vwap_position = "ABOVE"

        elif close < vwap_value:
            vwap_position = "BELOW"

        else:
            vwap_position = "AT_VWAP"

        # ==================================================
        # DI direction
        # ==================================================

        di_plus = float(
            latest["di_plus"]
        )

        di_minus = float(
            latest["di_minus"]
        )

        if di_plus > di_minus:
            directional_bias = "BULLISH"

        elif di_minus > di_plus:
            directional_bias = "BEARISH"

        else:
            directional_bias = "NEUTRAL"

        # ==================================================
        # ATR percentage
        # ==================================================

        atr_value = float(
            latest["atr"]
        )

        atr_percentage = (
            atr_value / close * 100
            if close > 0
            else 0
        )

        # ==================================================
        # Calculate Technical Score (0-100)
        # ==================================================

        # 1. Trend Score (0-25)
        if trend == "BULLISH":
            trend_score = 25
        elif trend == "MIXED":
            trend_score = 12
        else:  # BEARISH
            trend_score = 0

        # 2. RSI Score (0-20)
        if rsi_state == "EXTREME_OVERSOLD":
            rsi_score = 20
        elif rsi_state == "OVERSOLD":
            rsi_score = 15
        elif rsi_state == "RECOVERY_ZONE":
            rsi_score = 10
        elif rsi_state == "MOMENTUM":
            rsi_score = 5
        else:  # OVERBOUGHT
            rsi_score = 0

        # 3. MACD Score (0-20)
        if macd_state == "BULLISH_CROSS":
            macd_score = 20
        elif macd_state == "BULLISH":
            macd_score = 10
        else:  # BEARISH or BEARISH_CROSS
            macd_score = 0

        # 4. ADX Score (0-15)
        if adx_state == "STRONG_TREND":
            adx_score = 15
        elif adx_state == "DEVELOPING_TREND":
            adx_score = 8
        else:  # WEAK_TREND
            adx_score = 0

        # 5. Volume Score (0-10)
        if volume_state in ["EXTREME_SPIKE", "STRONG_SPIKE"]:
            volume_score = 10
        elif volume_state == "ELEVATED":
            volume_score = 5
        else:
            volume_score = 0

        # 6. OBV Score (0-10)
        if obv_state == "RISING":
            obv_score = 10
        elif obv_state == "FLAT":
            obv_score = 5
        else:  # FALLING
            obv_score = 0

        # Total Score (max 100)
        total_score = trend_score + rsi_score + macd_score + adx_score + volume_score + obv_score
        total_score = min(total_score, 100)

        # ==================================================
        # Result
        # ==================================================

        result = {
            "price": close,

            # ⭐ CRITICAL: These are required by Fusion Engine
            "score": total_score,
            "direction": trend,

            # Debug info (optional)
            "score_breakdown": {
                "trend": trend_score,
                "rsi": rsi_score,
                "macd": macd_score,
                "adx": adx_score,
                "volume": volume_score,
                "obv": obv_score,
            },

            "trend": trend,

            "ema": {
                "ema20": ema20,
                "ema50": ema50,
                "ema200": ema200,
            },

            "rsi": {
                "value": rsi,
                "state": rsi_state,
            },

            "macd": {
                "value": macd_value,
                "signal": macd_signal,
                "histogram": float(
                    latest["macd_histogram"]
                ),
                "state": macd_state,
            },

            "adx": {
                "value": adx_value,
                "state": adx_state,
            },

            "atr": {
                "value": atr_value,
                "percentage": atr_percentage,
            },

            "volume": {
                "ratio": volume_ratio,
                "state": volume_state,
            },

            "obv": {
                "value": obv_current,
                "state": obv_state,
            },

            "vwap": {
                "value": vwap_value,
                "position": vwap_position,
            },

            "directional_bias": directional_bias,

            "support": float(
                latest["recent_support"]
            ),

            "resistance": float(
                latest["recent_resistance"]
            ),
        }

        logger.info(
            "✅ Technical analysis complete | Trend: %s | RSI: %.1f | ADX: %.1f | Score: %.1f",
            trend,
            rsi,
            adx_value,
            total_score
        )

        return result
