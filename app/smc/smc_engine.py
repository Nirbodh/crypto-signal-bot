import logging
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd


logger = logging.getLogger("crypto-signal-bot")


class SMCEngine:
    """
    Production Smart Money Concepts Engine.

    Detects:
        - Swing High / Swing Low
        - BOS
        - CHoCH
        - Liquidity Sweeps
        - Displacement
        - Fair Value Gaps (FVG)
        - Order Blocks (OB)
        - Premium / Discount zones

    IMPORTANT
    ---------
    This engine produces SMC evidence only.

    It does NOT generate a final BUY/SELL signal.

    Output is intentionally compatible with:
        - SMCSetupValidator
        - SignalFusionEngine
    """

    def __init__(
        self,
        swing_length: int = 3,
        sweep_tolerance: float = 0.0015,
        displacement_atr_multiplier: float = 1.5,
        fvg_min_gap_pct: float = 0.001,
        order_block_lookback: int = 8,
        recent_window: int = 20,
    ) -> None:

        self.swing_length = max(
            2,
            int(swing_length),
        )

        self.sweep_tolerance = max(
            0.0,
            float(sweep_tolerance),
        )

        self.displacement_atr_multiplier = max(
            0.5,
            float(displacement_atr_multiplier),
        )

        self.fvg_min_gap_pct = max(
            0.0,
            float(fvg_min_gap_pct),
        )

        self.order_block_lookback = max(
            2,
            int(order_block_lookback),
        )

        self.recent_window = max(
            5,
            int(recent_window),
        )

    # ==========================================================
    # Validation
    # ==========================================================

    @staticmethod
    def _validate_dataframe(
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

        if not required.issubset(df.columns):
            return False

        return True

    # ==========================================================
    # Data Preparation
    # ==========================================================

    @staticmethod
    def _prepare_dataframe(
        df: pd.DataFrame,
    ) -> pd.DataFrame:

        data = df.copy()

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

        data = data.replace(
            [np.inf, -np.inf],
            np.nan,
        )

        data = data.dropna(
            subset=numeric_columns
        ).reset_index(drop=True)

        return data

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

        if len(data) < (
            length * 2 + 1
        ):
            return data

        for i in range(
            length,
            len(data) - length,
        ):

            current_high = float(
                data.iloc[i]["high"]
            )

            current_low = float(
                data.iloc[i]["low"]
            )

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

        structure_events: List[Dict[str, Any]] = []

        previous_swing_high: Optional[float] = None
        previous_swing_low: Optional[float] = None

        last_structure = "NEUTRAL"

        for index, row in data.iterrows():

            close = float(row["close"])

            # --------------------------------------------------
            # Bullish BOS
            # --------------------------------------------------

            if (
                previous_swing_high is not None
                and close > previous_swing_high
            ):

                structure_events.append({
                    "index": index,
                    "type": "BOS",
                    "direction": "BULLISH",
                    "level": previous_swing_high,
                })

                last_structure = "BULLISH"

                previous_swing_high = None

            # --------------------------------------------------
            # Bearish BOS
            # --------------------------------------------------

            if (
                previous_swing_low is not None
                and close < previous_swing_low
            ):

                structure_events.append({
                    "index": index,
                    "type": "BOS",
                    "direction": "BEARISH",
                    "level": previous_swing_low,
                })

                last_structure = "BEARISH"

                previous_swing_low = None

            # --------------------------------------------------
            # Register swing high
            # --------------------------------------------------

            if bool(row["swing_high"]):

                previous_swing_high = float(
                    row["high"]
                )

            # --------------------------------------------------
            # Register swing low
            # --------------------------------------------------

            if bool(row["swing_low"]):

                previous_swing_low = float(
                    row["low"]
                )

        # ------------------------------------------------------
        # CHoCH
        # ------------------------------------------------------

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

        swing_highs = data[
            data["swing_high"]
        ]

        swing_lows = data[
            data["swing_low"]
        ]

        return {
            "data": data,
            "events": structure_events,
            "last_structure": last_structure,
            "swing_highs": swing_highs,
            "swing_lows": swing_lows,
        }

    # ==========================================================
    # Liquidity Sweeps
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
        # High liquidity sweep
        # ------------------------------------------------------

        for index, row in data.iterrows():

            high = float(row["high"])
            close = float(row["close"])

            previous_highs = swing_highs[
                swing_highs.index < index
            ]

            if previous_highs.empty:
                continue

            level = float(
                previous_highs.iloc[-1]["high"]
            )

            tolerance = (
                level
                * self.sweep_tolerance
            )

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
        # Low liquidity sweep
        # ------------------------------------------------------

        for index, row in data.iterrows():

            low = float(row["low"])
            close = float(row["close"])

            previous_lows = swing_lows[
                swing_lows.index < index
            ]

            if previous_lows.empty:
                continue

            level = float(
                previous_lows.iloc[-1]["low"]
            )

            tolerance = (
                level
                * self.sweep_tolerance
            )

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
    # ATR
    # ==========================================================

    @staticmethod
    def _calculate_atr(
        df: pd.DataFrame,
        period: int = 14,
    ) -> pd.Series:

        previous_close = df[
            "close"
        ].shift(1)

        true_range = pd.concat(
            [
                df["high"] - df["low"],

                (
                    df["high"]
                    - previous_close
                ).abs(),

                (
                    df["low"]
                    - previous_close
                ).abs(),
            ],
            axis=1,
        ).max(axis=1)

        return true_range.rolling(
            period
        ).mean()

    # ==========================================================
    # Displacement
    # ==========================================================

    def detect_displacement(
        self,
        df: pd.DataFrame,
    ) -> List[Dict[str, Any]]:

        data = df.copy()

        data["atr_internal"] = (
            self._calculate_atr(data)
        )

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

            atr_value = float(
                atr_value
            )

            if atr_value <= 0:
                continue

            body = float(
                row["candle_body"]
            )

            strength = (
                body / atr_value
            )

            if strength < (
                self.displacement_atr_multiplier
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
                "atr": atr_value,
                "strength": strength,
            })

        return events

    # ==========================================================
    # Fair Value Gap
    # ==========================================================

    def detect_fair_value_gaps(
        self,
        df: pd.DataFrame,
    ) -> List[Dict[str, Any]]:

        data = df.copy()

        fvgs: List[Dict[str, Any]] = []

        if len(data) < 3:
            return fvgs

        for i in range(
            2,
            len(data),
        ):

            first = data.iloc[i - 2]
            middle = data.iloc[i - 1]
            current = data.iloc[i]

            # --------------------------------------------------
            # Bullish FVG
            #
            # Current low > first candle high
            # --------------------------------------------------

            bullish_gap = (
                float(current["low"])
                - float(first["high"])
            )

            if bullish_gap > 0:

                lower = float(
                    first["high"]
                )

                upper = float(
                    current["low"]
                )

                midpoint = (
                    lower + upper
                ) / 2.0

                reference_price = float(
                    current["close"]
                )

                gap_pct = (
                    bullish_gap
                    / reference_price
                    if reference_price > 0
                    else 0
                )

                if (
                    gap_pct
                    >= self.fvg_min_gap_pct
                ):

                    fvgs.append({
                        "index": i,
                        "type": "FVG",
                        "direction": "BULLISH",
                        "lower": lower,
                        "upper": upper,
                        "midpoint": midpoint,
                        "gap_size": bullish_gap,
                        "gap_pct": gap_pct * 100.0,
                        "mitigated": False,
                    })

            # --------------------------------------------------
            # Bearish FVG
            #
            # Current high < first candle low
            # --------------------------------------------------

            bearish_gap = (
                float(first["low"])
                - float(current["high"])
            )

            if bearish_gap > 0:

                lower = float(
                    current["high"]
                )

                upper = float(
                    first["low"]
                )

                midpoint = (
                    lower + upper
                ) / 2.0

                reference_price = float(
                    current["close"]
                )

                gap_pct = (
                    bearish_gap
                    / reference_price
                    if reference_price > 0
                    else 0
                )

                if (
                    gap_pct
                    >= self.fvg_min_gap_pct
                ):

                    fvgs.append({
                        "index": i,
                        "type": "FVG",
                        "direction": "BEARISH",
                        "lower": lower,
                        "upper": upper,
                        "midpoint": midpoint,
                        "gap_size": bearish_gap,
                        "gap_pct": gap_pct * 100.0,
                        "mitigated": False,
                    })

        # ------------------------------------------------------
        # Mitigation
        # ------------------------------------------------------

        for gap in fvgs:

            start = gap["index"] + 1

            for j in range(
                start,
                len(data),
            ):

                candle_high = float(
                    data.iloc[j]["high"]
                )

                candle_low = float(
                    data.iloc[j]["low"]
                )

                if gap["direction"] == "BULLISH":

                    # Price traded back into / through
                    # the bullish FVG.

                    if (
                        candle_low
                        <= gap["upper"]
                    ):

                        gap["mitigated"] = True
                        break

                else:

                    if (
                        candle_high
                        >= gap["lower"]
                    ):

                        gap["mitigated"] = True
                        break

        return fvgs

    # ==========================================================
    # Order Blocks
    # ==========================================================

    def detect_order_blocks(
        self,
        df: pd.DataFrame,
        structure_events: Optional[
            List[Dict[str, Any]]
        ] = None,
    ) -> List[Dict[str, Any]]:

        data = df.copy()

        structure_events = (
            structure_events or []
        )

        order_blocks: List[
            Dict[str, Any]
        ] = []

        # ------------------------------------------------------
        # Use BOS / CHoCH as confirmation.
        #
        # Bullish OB:
        # last bearish candle before bullish
        # structure displacement/break.
        #
        # Bearish OB:
        # last bullish candle before bearish
        # structure displacement/break.
        # ------------------------------------------------------

        for event in structure_events:

            if event["type"] not in {
                "BOS",
                "CHoCH",
            }:
                continue

            event_index = event["index"]

            try:
                event_position = data.index.get_loc(
                    event_index
                )
            except (
                KeyError,
                TypeError,
            ):
                continue

            start = max(
                0,
                event_position
                - self.order_block_lookback,
            )

            candidates = data.iloc[
                start:event_position
            ]

            if candidates.empty:
                continue

            if event["direction"] == "BULLISH":

                opposite = candidates[
                    candidates["close"]
                    < candidates["open"]
                ]

                if opposite.empty:
                    continue

                candle = opposite.iloc[-1]

                lower = float(
                    candle["low"]
                )

                upper = float(
                    candle["high"]
                )

                order_blocks.append({
                    "index": int(
                        candle.name
                    ),
                    "type": "ORDER_BLOCK",
                    "direction": "BULLISH",
                    "lower": lower,
                    "upper": upper,
                    "midpoint": (
                        lower + upper
                    ) / 2.0,
                    "mitigated": False,
                    "confirmation_index": event_index,
                })

            elif event["direction"] == "BEARISH":

                opposite = candidates[
                    candidates["close"]
                    > candidates["open"]
                ]

                if opposite.empty:
                    continue

                candle = opposite.iloc[-1]

                lower = float(
                    candle["low"]
                )

                upper = float(
                    candle["high"]
                )

                order_blocks.append({
                    "index": int(
                        candle.name
                    ),
                    "type": "ORDER_BLOCK",
                    "direction": "BEARISH",
                    "lower": lower,
                    "upper": upper,
                    "midpoint": (
                        lower + upper
                    ) / 2.0,
                    "mitigated": False,
                    "confirmation_index": event_index,
                })

        # ------------------------------------------------------
        # Remove duplicates
        # ------------------------------------------------------

        unique = {}

        for block in order_blocks:

            key = (
                block["index"],
                block["direction"],
            )

            unique[key] = block

        order_blocks = list(
            unique.values()
        )

        order_blocks.sort(
            key=lambda x: x["index"]
        )

        # ------------------------------------------------------
        # Mitigation
        # ------------------------------------------------------

        for block in order_blocks:

            start = block["index"] + 1

            for j in range(
                start,
                len(data),
            ):

                candle_high = float(
                    data.iloc[j]["high"]
                )

                candle_low = float(
                    data.iloc[j]["low"]
                )

                if (
                    candle_low
                    <= block["upper"]
                    and candle_high
                    >= block["lower"]
                ):

                    block["mitigated"] = True
                    break

        return order_blocks

    # ==========================================================
    # Premium / Discount
    # ==========================================================

    def calculate_premium_discount(
        self,
        df: pd.DataFrame,
        lookback: int = 50,
    ) -> Dict[str, Any]:

        data = df.tail(
            max(10, int(lookback))
        )

        if data.empty:
            return {
                "state": "UNKNOWN",
                "range_high": None,
                "range_low": None,
                "equilibrium": None,
                "position": None,
            }

        range_high = float(
            data["high"].max()
        )

        range_low = float(
            data["low"].min()
        )

        equilibrium = (
            range_high + range_low
        ) / 2.0

        current_price = float(
            data.iloc[-1]["close"]
        )

        if current_price > equilibrium:

            state = "PREMIUM"

        elif current_price < equilibrium:

            state = "DISCOUNT"

        else:

            state = "EQUILIBRIUM"

        return {
            "state": state,
            "range_high": range_high,
            "range_low": range_low,
            "equilibrium": equilibrium,
            "current_price": current_price,
        }

    # ==========================================================
    # Recent Event Builder
    # ==========================================================

    def _build_recent(
        self,
        df: pd.DataFrame,
        structure_events: List[Dict[str, Any]],
        sweeps: List[Dict[str, Any]],
        displacement: List[Dict[str, Any]],
        fvgs: List[Dict[str, Any]],
        order_blocks: List[Dict[str, Any]],
    ) -> Dict[str, Any]:

        latest_index = df.index[-1]

        cutoff = (
            latest_index
            - self.recent_window
        )

        recent_structure = [
            event
            for event in structure_events
            if event["index"] >= cutoff
        ]

        recent_sweeps = [
            event
            for event in sweeps
            if event["index"] >= cutoff
        ]

        recent_displacement = [
            event
            for event in displacement
            if event["index"] >= cutoff
        ]

        recent_fvgs = [
            gap
            for gap in fvgs
            if gap["index"] >= cutoff
        ]

        recent_order_blocks = [
            block
            for block in order_blocks
            if (
                block["index"] >= cutoff
                or block.get(
                    "confirmation_index",
                    -1,
                ) >= cutoff
            )
        ]

        # ------------------------------------------------------
        # Unified events
        # ------------------------------------------------------

        events = (
            recent_structure
            + recent_sweeps
            + recent_displacement
        )

        events.sort(
            key=lambda x: x["index"]
        )

        return {
            "events": events,

            "structure": recent_structure,

            "sweeps": recent_sweeps,

            "fvg": recent_fvgs,

            "order_blocks": recent_order_blocks,

            # --------------------------------------------------
            # Backward-compatible boolean fields
            # --------------------------------------------------

            "bullish_sweep": any(
                event["type"]
                == "LIQUIDITY_SWEEP"
                and event["direction"]
                == "BULLISH"
                for event in recent_sweeps
            ),

            "bearish_sweep": any(
                event["type"]
                == "LIQUIDITY_SWEEP"
                and event["direction"]
                == "BEARISH"
                for event in recent_sweeps
            ),

            "bullish_displacement": any(
                event["type"]
                == "DISPLACEMENT"
                and event["direction"]
                == "BULLISH"
                for event in recent_displacement
            ),

            "bearish_displacement": any(
                event["type"]
                == "DISPLACEMENT"
                and event["direction"]
                == "BEARISH"
                for event in recent_displacement
            ),

            "choch": any(
                event["type"] == "CHoCH"
                for event in recent_structure
            ),
        }

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

        data = self._prepare_dataframe(df)

        # SMC requires enough candles for:
        # swings + ATR + structure + OB/FVG.

        minimum_candles = max(
            100,
            self.swing_length * 2 + 20,
        )

        if len(data) < minimum_candles:

            logger.warning(
                "⚠️ SMC requires more candles: %s (minimum %s)",
                len(data),
                minimum_candles,
            )

            return None

        # ======================================================
        # Core detection
        # ======================================================

        structure = self.detect_structure(
            data
        )

        sweeps = self.detect_liquidity_sweeps(
            data
        )

        displacement = (
            self.detect_displacement(
                data
            )
        )

        fvgs = self.detect_fair_value_gaps(
            data
        )

        order_blocks = (
            self.detect_order_blocks(
                data,
                structure["events"],
            )
        )

        premium_discount = (
            self.calculate_premium_discount(
                data
            )
        )

        # ======================================================
        # Recent data
        # ======================================================

        recent = self._build_recent(
            data,
            structure["events"],
            sweeps,
            displacement,
            fvgs,
            order_blocks,
        )

        # ======================================================
        # Directional flags
        # ======================================================

        recent_events = recent[
            "events"
        ]

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

        recent_bullish_structure = any(
            event["type"]
            in {"BOS", "CHoCH"}
            and event["direction"]
            == "BULLISH"
            for event in recent_events
        )

        recent_bearish_structure = any(
            event["type"]
            in {"BOS", "CHoCH"}
            and event["direction"]
            == "BEARISH"
            for event in recent_events
        )

        # ======================================================
        # Return
        # ======================================================

        result = {

            "status": "SUCCESS",

            "last_structure":
                structure[
                    "last_structure"
                ],

            "swing_high_count":
                len(
                    structure[
                        "swing_highs"
                    ]
                ),

            "swing_low_count":
                len(
                    structure[
                        "swing_lows"
                    ]
                ),

            "bos_choch_events":
                structure[
                    "events"
                ],

            "liquidity_sweeps":
                sweeps,

            "displacement_events":
                displacement,

            "fvg":
                fvgs,

            "order_blocks":
                order_blocks,

            "premium_discount":
                premium_discount,

            "recent":
                recent,

            "event_count":
                len(
                    structure[
                        "events"
                    ]
                ),

            # --------------------------------------------------
            # Top-level directional evidence
            # --------------------------------------------------

            "recent_bullish_sweep":
                recent_bullish_sweep,

            "recent_bearish_sweep":
                recent_bearish_sweep,

            "recent_bullish_displacement":
                recent_bullish_displacement,

            "recent_bearish_displacement":
                recent_bearish_displacement,

            "recent_bullish_structure":
                recent_bullish_structure,

            "recent_bearish_structure":
                recent_bearish_structure,

            "current_price":
                float(
                    data.iloc[-1]["close"]
                ),
        }

        logger.info(
            (
                "SMC analysis complete | "
                "structure=%s | "
                "BOS/CHoCH=%s | "
                "sweeps=%s | "
                "FVG=%s | "
                "OB=%s | "
                "PD=%s"
            ),
            structure["last_structure"],
            len(structure["events"]),
            len(sweeps),
            len(fvgs),
            len(order_blocks),
            premium_discount["state"],
        )

        return result
