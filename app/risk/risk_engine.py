import logging
from typing import Any, Dict, Optional


logger = logging.getLogger("crypto-signal-bot")


class RiskEngine:
    """
    Capital protection and position sizing engine.

    Important:
    Leverage does NOT determine the initial trading risk.

    Risk is primarily determined by:

        Entry
        Stop Loss
        Position Size

    Leverage only affects required margin.
    """

    def __init__(
        self,
        default_risk_percent: float = 1.0,
        max_risk_percent: float = 2.0,
        max_position_percent: float = 25.0,
        max_leverage: float = 10.0,
    ):

        self.default_risk_percent = (
            default_risk_percent
        )

        self.max_risk_percent = (
            max_risk_percent
        )

        self.max_position_percent = (
            max_position_percent
        )

        self.max_leverage = (
            max_leverage
        )

    # ==========================================================
    # Helpers
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
    # Risk percentage
    # ==========================================================

    def _get_risk_percent(
        self,
        signal_score: Optional[float],
        requested_risk_percent: Optional[float],
    ) -> float:

        if requested_risk_percent is not None:

            risk = self._number(
                requested_risk_percent
            )

        else:

            risk = None

        if risk is None:

            risk = (
                self.default_risk_percent
            )

        # ------------------------------------------------------
        # Score-based adjustment
        # ------------------------------------------------------

        if signal_score is not None:

            score = self._number(
                signal_score
            )

            if score is not None:

                if score >= 90:

                    risk = min(
                        risk,
                        self.max_risk_percent,
                    )

                elif score >= 80:

                    risk = min(
                        risk,
                        1.5,
                    )

                elif score >= 70:

                    risk = min(
                        risk,
                        1.0,
                    )

                else:

                    risk = min(
                        risk,
                        0.5,
                    )

        return max(
            0.0,
            min(
                risk,
                self.max_risk_percent,
            ),
        )

    # ==========================================================
    # Position sizing
    # ==========================================================

    def calculate_position_size(
        self,
        account_balance: Any,
        entry_price: Any,
        stop_loss: Any,
        signal_score: Optional[Any] = None,
        requested_risk_percent: Optional[Any] = None,
    ) -> Dict[str, Any]:

        balance = self._number(
            account_balance
        )

        entry = self._number(
            entry_price
        )

        sl = self._number(
            stop_loss
        )

        score = self._number(
            signal_score
        )

        if (
            balance is None
            or balance <= 0
        ):

            return {
                "status": "INVALID",
                "reason": (
                    "Invalid account balance"
                ),
            }

        if (
            entry is None
            or entry <= 0
        ):

            return {
                "status": "INVALID",
                "reason": (
                    "Invalid entry price"
                ),
            }

        if (
            sl is None
            or sl <= 0
        ):

            return {
                "status": "INVALID",
                "reason": (
                    "Invalid stop loss"
                ),
            }

        # ------------------------------------------------------
        # Risk amount
        # ------------------------------------------------------

        risk_percent = (
            self._get_risk_percent(
                score,
                self._number(
                    requested_risk_percent
                ),
            )
        )

        risk_amount = (
            balance
            * risk_percent
            / 100
        )

        # ------------------------------------------------------
        # Price distance
        # ------------------------------------------------------

        price_distance = abs(
            entry - sl
        )

        if price_distance <= 0:

            return {
                "status": "INVALID",
                "reason": (
                    "Entry and SL cannot be equal"
                ),
            }

        stop_distance_percent = (
            price_distance
            / entry
        ) * 100

        # ------------------------------------------------------
        # Position size
        #
        # Example:
        #
        # Risk = $10
        # Entry = $100
        # SL = $95
        #
        # Risk/unit = $5
        #
        # Position = $10 / $5
        #          = 2 units
        # ------------------------------------------------------

        quantity = (
            risk_amount
            / price_distance
        )

        position_notional = (
            quantity
            * entry
        )

        # ------------------------------------------------------
        # Maximum position cap
        # ------------------------------------------------------

        max_position_notional = (
            balance
            * self.max_position_percent
            / 100
        )

        capped = False

        if (
            position_notional
            > max_position_notional
        ):

            position_notional = (
                max_position_notional
            )

            quantity = (
                position_notional
                / entry
            )

            capped = True

        # ------------------------------------------------------
        # Actual estimated loss
        # ------------------------------------------------------

        estimated_loss = (
            quantity
            * price_distance
        )

        actual_risk_percent = (
            estimated_loss
            / balance
        ) * 100

        return {
            "status": "SUCCESS",

            "account_balance": round(
                balance,
                8,
            ),

            "risk_percent": round(
                actual_risk_percent,
                4,
            ),

            "risk_amount": round(
                estimated_loss,
                8,
            ),

            "entry": round(
                entry,
                12,
            ),

            "stop_loss": round(
                sl,
                12,
            ),

            "stop_distance_percent": round(
                stop_distance_percent,
                4,
            ),

            "quantity": round(
                quantity,
                12,
            ),

            "position_notional": round(
                position_notional,
                8,
            ),

            "position_capped": capped,

            "signal_score": score,
        }

    # ==========================================================
    # Leverage / margin calculation
    # ==========================================================

    def calculate_leverage_plan(
        self,
        position_notional: Any,
        requested_leverage: Optional[Any] = None,
    ) -> Dict[str, Any]:

        notional = self._number(
            position_notional
        )

        leverage = self._number(
            requested_leverage
        )

        if (
            notional is None
            or notional <= 0
        ):

            return {
                "status": "INVALID",
                "reason": (
                    "Invalid position notional"
                ),
            }

        if leverage is None:

            leverage = 1.0

        leverage = max(
            1.0,
            min(
                leverage,
                self.max_leverage,
            ),
        )

        margin_required = (
            notional
            / leverage
        )

        return {
            "status": "SUCCESS",

            "leverage": leverage,

            "position_notional": round(
                notional,
                8,
            ),

            "estimated_margin": round(
                margin_required,
                8,
            ),

            "max_allowed_leverage": (
                self.max_leverage
            ),
        }

    # ==========================================================
    # Full plan
    # ==========================================================

    def build_plan(
        self,
        account_balance: Any,
        entry_price: Any,
        stop_loss: Any,
        signal_score: Optional[Any] = None,
        requested_risk_percent: Optional[Any] = None,
        requested_leverage: Optional[Any] = None,
    ) -> Dict[str, Any]:

        position = (
            self.calculate_position_size(
                account_balance=account_balance,
                entry_price=entry_price,
                stop_loss=stop_loss,
                signal_score=signal_score,
                requested_risk_percent=(
                    requested_risk_percent
                ),
            )
        )

        if (
            position["status"]
            != "SUCCESS"
        ):

            return position

        leverage = (
            self.calculate_leverage_plan(
                position[
                    "position_notional"
                ],
                requested_leverage,
            )
        )

        warnings = []

        if position[
            "position_capped"
        ]:

            warnings.append(
                "Position size capped by maximum notional limit"
            )

        if (
            position[
                "stop_distance_percent"
            ]
            > 8
        ):

            warnings.append(
                "Wide stop distance"
            )

        if (
            leverage["leverage"]
            >= self.max_leverage
        ):

            warnings.append(
                "Maximum configured leverage reached"
            )

        return {
            "status": "SUCCESS",
            "decision": "APPROVE",
            "position": position,
            "leverage": leverage,
            "warnings": warnings,
        }

    # ==========================================================
    # Evaluate method for scanner compatibility
    # ==========================================================

    def evaluate(
        self,
        symbol: Optional[str] = None,
        fusion_result: Optional[Dict[str, Any]] = None,
        gemini_result: Optional[Dict[str, Any]] = None,
        trade_plan: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:

        """
        Evaluate risk for a potential trade.

        This method is called by ScannerEngine.
        """

        # If fusion_result is provided, extract data
        if fusion_result:
            score = fusion_result.get("score", 0)
            direction = fusion_result.get("direction", "NEUTRAL")
        else:
            score = 0
            direction = "NEUTRAL"

        # Default values if trade_plan is not available
        entry_price = 0
        stop_loss = 0

        if trade_plan:
            entry_price = trade_plan.get("entry", 0)
            stop_loss = trade_plan.get("stop_loss", 0)

        # Use default account balance
        account_balance = 10000.0

        # Build risk plan
        if entry_price > 0 and stop_loss > 0:
            plan = self.build_plan(
                account_balance=account_balance,
                entry_price=entry_price,
                stop_loss=stop_loss,
                signal_score=score,
            )
        else:
            plan = {
                "status": "INVALID",
                "decision": "REJECT",
                "reason": "Missing entry or stop loss",
            }

        # Check if risk is acceptable
        if plan.get("status") == "SUCCESS":
            # Check if stop distance is reasonable
            stop_distance = plan.get("position", {}).get("stop_distance_percent", 0)
            if stop_distance > 10:
                plan["decision"] = "REJECT"
                plan["reason"] = "Stop distance too wide"
            else:
                plan["decision"] = "APPROVE"
        else:
            plan["decision"] = "REJECT"

        return plan
