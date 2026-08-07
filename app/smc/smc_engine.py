import logging
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd


logger = logging.getLogger("crypto-signal-bot")


class SMCEngine:
    """
    Smart Money Concepts core engine.

    Detects:
    - Swing High / Swing Low
    - Break of Structure (BOS)
    - Change of Character (CHoCH)
    - Liquidity Sweeps
    - Basic displacement

    IMPORTANT:
    This engine does NOT generate a final BUY/SELL signal.
    It produces SMC evidence for the later fusion engine.
    """

    def __init__(
        self,
        swing_length: int = 3,
        sweep_tolerance: float = 0.0015,
        displacement_atr_multiplier: float = 1.5,
    ):
        self.swing_length = swing_length
        self.sweep_tolerance = sweep_tolerance
        self.displacement_atr_multiplier = (
            displacement_atr_multiplier
        )

    # ==========================================================
    # Validation
    # ==========================================================

    def _validate_dataframe(
        self,
        df: pd.DataFrame,
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

        return required.issubset(df.columns)

    # ==========================================================
    # Swing Detection
    # ==========================================================

    def detect_swings(
        self,
        df: pd.DataFrame,
    ) -> pd.DataFrame:

        data = df.copy()

        length = self.swing_length

        data["swing_high"] = False
        data["swing_low"] = False

        for i in range(
            length,
            len(data) - length,
        ):

            current_high = data.iloc[i]["high"]
            current_low = data.iloc[i]["low"]

            left_highs = data.iloc[
                i - length:i
            ]["high"]

            right_highs = data.iloc[
                i + 1:i + length + 1
            ]["high"]

            left_lows = data.iloc[
                i - length:i
            ]["low"]

            right_lows = data.iloc[
                i + 1:i + length + 1
            ]["low"]

            if (
                current_high > left_highs.max()
                and current_high > right_highs.max()
            ):
                data.at[
                    data.index[i],
                    "swing_high",
                ] = True

            if (
                current_low < left_lows.min()
                and current_low < right_lows.min()
            ):
                data.at[
                    data.index[i],
                    "swing_low",
                ] = True

        return data

    # ==========================================================
    # Market Structure
    # ==========================================================

    def detect_structure(
        self,
        df: pd.DataFrame,
    ) -> Dict[str, Any]:

        data = self.detect_swings(df)

        swing_highs = data[
            data["swing_high"]
        ]

        swing_lows = data[
            data["swing_low"]
        ]

        structure_events: List[Dict[str, Any]] = []

        last_structure = "NEUTRAL"

        previous_swing_high: Optional[float] = None
        previous_swing_low: Optional[float] = None

        for index, row in data.iterrows():

            close = float(row["close"])

            # ----------------------------------------------
            # Bullish structure break
            # ----------------------------------------------

            if (
                previous_swing_high is not None
                and close > previous_swing_high
            ):

                event = {
                    "index": index,
                    "type": "BOS",
                    "direction": "BULLISH",
                    "level": previous_swing_high,
                }

                structure_events.append(event)

                last_structure = "BULLISH"

                previous_swing_high = None

            # ----------------------------------------------
            # Bearish structure break
            # ----------------------------------------------

            if (
                previous_swing_low is not None
                and close < previous_swing_low
            ):

                event = {
                    "index": index,
                    "type": "BOS",
                    "direction": "BEARISH",
                    "level": previous_swing_low,
                }

                structure_events.append(event)

                last_structure = "BEARISH"

                previous_swing_low = None

            # ----------------------------------------------
            # Register new swing high
            # ----------------------------------------------

            if bool(row["swing_high"]):

                previous_swing_high = float(
                    row["high"]
                )

            # ----------------------------------------------
            # Register new swing low
            # ----------------------------------------------

            if bool(row["swing_low"]):

                previous_swing_low = float(
                    row["low"]
                )

        # ==================================================
        # CHoCH detection
        # ==================================================

        for i in range(
            1,
            len(structure_events),
        ):

            current = structure_events[i]
            previous = structure_events[i - 1]

            if (
                current["direction"]
                != previous["direction"]
            ):

                current["type"] = "CHoCH"

        return {
            "data": data,
            "events": structure_events,
            "last_structure": last_structure,
            "swing_highs": swing_highs,
            "swing_lows": swing_lows,
        }

    # ==========================================================
    # Liquidity Sweep Detection
    # ==========================================================

    def detect_liquidity_sweeps(
        self,
        df: pd.DataFrame,
    ) -> List[Dict[str, Any]]:

        data = self.detect_swings(df)

        swing_highs = data[
            data["swing_high"]
        ]

        swing_lows = data[
            data["swing_low"]
        ]

        sweeps: List[Dict[str, Any]] = []

        # ------------------------------------------------------
        # Sweep previous highs
        # ------------------------------------------------------

        for index, row in data.iterrows():

            high = float(row["high"])
            close = float(row["close"])

            previous_highs = swing_highs[
                swing_highs.index < index
            ]

            if not previous_highs.empty:

                level = float(
                    previous_highs.iloc[-1]["high"]
                )

                tolerance = (
                    level
                    * self.sweep_tolerance
                )

                # Price trades above liquidity,
                # then closes back below it.

                if (
                    high > level + tolerance
                    and close < level
                ):

                    sweeps.append({
                        "index": index,
                        "type": "LIQUIDITY_SWEEP",
                        "direction": "BEARISH",
                        "swept_level": level,
                    })

        # ------------------------------------------------------
        # Sweep previous lows
        # ------------------------------------------------------

        for index, row in data.iterrows():

            low = float(row["low"])
            close = float(row["close"])

            previous_lows = swing_lows[
                swing_lows.index < index
            ]

            if not previous_lows.empty:

                level = float(
                    previous_lows.iloc[-1]["low"]
                )

                tolerance = (
                    level
                    * self.sweep_tolerance
                )

                # Price trades below liquidity,
                # then closes back above it.

                if (
                    low < level - tolerance
                    and close > level
                ):

                    sweeps.append({
                        "index": index,
                        "type": "LIQUIDITY_SWEEP",
                        "direction": "BULLISH",
                        "swept_level": level,
                    })

        sweeps.sort(
            key=lambda x: x["index"]
        )

        return sweeps

    # ==========================================================
    # Displacement
    # ==========================================================

    def detect_displacement(
        self,
        df: pd.DataFrame,
    ) -> List[Dict[str, Any]]:

        data = df.copy()

        # Calculate ATR internally so this engine
        # does not depend on TechnicalEngine.

        previous_close = data[
            "close"
        ].shift(1)

        true_range = pd.concat(
            [
                data["high"] - data["low"],
                (
                    data["high"]
                    - previous_close
                ).abs(),
                (
                    data["low"]
                    - previous_close
                ).abs(),
            ],
            axis=1,
        ).max(axis=1)

        atr = (
            true_range
            .rolling(14)
            .mean()
        )

        data["atr_internal"] = atr

        data["candle_body"] = (
            data["close"]
            - data["open"]
        ).abs()

        events: List[Dict[str, Any]] = []

        for index, row in data.iterrows():

            atr_value = row[
                "atr_internal"
            ]

            if pd.isna(atr_value):
                continue

            body = float(
                row["candle_body"]
            )

            if body < (
                float(atr_value)
                * self.displacement_atr_multiplier
            ):
                continue

            if row["close"] > row["open"]:

                direction = "BULLISH"

            elif row["close"] < row["open"]:

                direction = "BEARISH"

            else:
                continue

            events.append({
                "index": index,
                "type": "DISPLACEMENT",
                "direction": direction,
                "body_size": body,
                "atr": float(atr_value),
                "strength": (
                    body / float(atr_value)
                ),
            })

        return events

    # ==========================================================
    # Main Analysis
    # ==========================================================

    def analyze(
        self,
        df: pd.DataFrame,
    ) -> Optional[Dict[str, Any]]:

        if not self._validate_dataframe(df):

            logger.error(
                "❌ Invalid OHLCV dataframe for SMC."
            )

            return None

        if len(df) < 100:

            logger.warning(
                "⚠️ SMC requires more candles: %s",
                len(df),
            )

            return None

        structure = self.detect_structure(df)

        sweeps = self.detect_liquidity_sweeps(df)

        displacement = (
            self.detect_displacement(df)
        )

        latest_index = df.index[-1]

        recent_events = []

        for event in (
            structure["events"]
            + sweeps
            + displacement
        ):

            if event["index"] >= (
                latest_index - 20
            ):
                recent_events.append(event)

        # ------------------------------------------------------
        # Latest relevant events
        # ------------------------------------------------------

        recent_bullish_sweep = any(
            event["type"]
            == "LIQUIDITY_SWEEP"
            and event["direction"]
            == "BULLISH"
            for event in recent_events
        )

        recent_bearish_sweep = any(
            event["type"]
            == "LIQUIDITY_SWEEP"
            and event["direction"]
            == "BEARISH"
            for event in recent_events
        )

        recent_bullish_displacement = any(
            event["type"]
            == "DISPLACEMENT"
            and event["direction"]
            == "BULLISH"
            for event in recent_events
        )

        recent_bearish_displacement = any(
            event["type"]
            == "DISPLACEMENT"
            and event["direction"]
            == "BEARISH"
            for event in recent_events
        )

        recent_choch = any(
            event["type"] == "CHoCH"
            for event in recent_events
        )

        return {
            "last_structure": (
                structure["last_structure"]
            ),

            "swing_high_count": len(
                structure["swing_highs"]
            ),

            "swing_low_count": len(
                structure["swing_lows"]
            ),

            "bos_choch_events": (
                structure["events"]
            ),

            "liquidity_sweeps": sweeps,

            "displacement_events": displacement,

            "recent": {
                "bullish_sweep": (
                    recent_bullish_sweep
                ),
                "bearish_sweep": (
                    recent_bearish_sweep
                ),
                "bullish_displacement": (
                    recent_bullish_displacement
                ),
                "bearish_displacement": (
                    recent_bearish_displacement
                ),
                "choch": recent_choch,
            },

            "event_count": len(
                structure["events"]
            ),
        }
