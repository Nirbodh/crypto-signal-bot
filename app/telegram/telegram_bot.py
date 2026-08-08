import html
import logging
import os
from typing import Any, Dict, Optional

import requests


logger = logging.getLogger("crypto-signal-bot")


class TelegramBot:
    """
    Production Telegram notification service.

    Responsibilities:
        - Format signals
        - Send trading signals
        - Send system/status messages
        - Never calculate signals

    Compatible with:
        SignalFusionEngine
        ScannerEngine
        GeminiReviewer
        TradePlanEngine
        RiskEngine
    """

    def __init__(
        self,
        bot_token: Optional[str] = None,
        chat_id: Optional[str] = None,
        timeout: int = 10,
    ):

        self.bot_token = (
            bot_token
            or os.getenv("TELEGRAM_BOT_TOKEN")
        )

        self.chat_id = (
            chat_id
            or os.getenv("TELEGRAM_CHAT_ID")
        )

        self.timeout = max(
            3,
            int(timeout),
        )

        self.base_url = (
            "https://api.telegram.org"
        )

    # ==========================================================
    # Configuration
    # ==========================================================

    @property
    def configured(self) -> bool:
        return bool(
            self.bot_token
            and self.chat_id
        )

    # ==========================================================
    # Safe formatting helpers
    # ==========================================================

    @staticmethod
    def _safe_text(
        value: Any,
        default: str = "-",
    ) -> str:
        """
        Safely convert arbitrary values to Telegram HTML-safe text.
        """

        if value is None:
            return default

        text = str(value).strip()

        if not text:
            return default

        return html.escape(text)

    @staticmethod
    def _safe_number(
        value: Any,
        default: str = "-",
    ) -> str:
        """
        Format numeric values without crashing.
        """

        if value is None:
            return default

        try:
            number = float(value)

        except (
            TypeError,
            ValueError,
        ):
            return TelegramBot._safe_text(
                value,
                default,
            )

        if number.is_integer():
            return str(int(number))

        return f"{number:.4f}".rstrip("0").rstrip(".")

    @staticmethod
    def _get_dict(
        value: Any,
    ) -> Dict[str, Any]:
        if isinstance(value, dict):
            return value

        return {}

    # ==========================================================
    # Send message
    # ==========================================================

    def send_message(
        self,
        text: str,
        disable_web_page_preview: bool = True,
    ) -> Dict[str, Any]:

        if not self.configured:

            logger.warning(
                "⚠️ Telegram credentials are not configured"
            )

            return {
                "status": "SKIPPED",
                "reason": (
                    "Telegram credentials not configured"
                ),
            }

        if not text:

            return {
                "status": "SKIPPED",
                "reason": "Empty Telegram message",
            }

        url = (
            f"{self.base_url}/bot"
            f"{self.bot_token}/sendMessage"
        )

        payload = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": (
                disable_web_page_preview
            ),
        }

        try:

            response = requests.post(
                url,
                json=payload,
                timeout=self.timeout,
            )

            response.raise_for_status()

            data = response.json()

            if data.get("ok"):

                return {
                    "status": "SUCCESS",
                    "message_id": (
                        data
                        .get("result", {})
                        .get("message_id")
                    ),
                }

            reason = data.get(
                "description",
                "Telegram API error",
            )

            logger.warning(
                "Telegram API rejected message: %s",
                reason,
            )

            return {
                "status": "FAILED",
                "reason": reason,
            }

        except requests.RequestException as exc:

            logger.warning(
                "Telegram request failed: %s",
                exc,
            )

            return {
                "status": "FAILED",
                "reason": str(exc),
            }

        except ValueError as exc:

            logger.warning(
                "Telegram returned invalid JSON: %s",
                exc,
            )

            return {
                "status": "FAILED",
                "reason": (
                    "Invalid Telegram API response"
                ),
            }

    # ==========================================================
    # Signal formatter
    # ==========================================================

    def format_signal(
        self,
        signal: Dict[str, Any],
    ) -> str:
        """
        Format the complete ScannerEngine result.

        Important:
        Fusion data normally lives under:

            signal["fusion"]

        not directly under signal.
        """

        signal = self._get_dict(signal)

        # ------------------------------------------------------
        # Basic signal information
        # ------------------------------------------------------

        symbol = self._safe_text(
            signal.get(
                "symbol",
                "UNKNOWN",
            ),
            "UNKNOWN",
        )

        direction = str(
            signal.get(
                "direction",
                "NEUTRAL",
            )
        ).upper()

        # Support both fusion terminology and
        # execution terminology.

        if direction == "BULLISH":

            direction_text = (
                "🟢 <b>LONG / BULLISH</b>"
            )

        elif direction == "BEARISH":

            direction_text = (
                "🔴 <b>SHORT / BEARISH</b>"
            )

        elif direction == "LONG":

            direction_text = (
                "🟢 <b>LONG</b>"
            )

        elif direction == "SHORT":

            direction_text = (
                "🔴 <b>SHORT</b>"
            )

        else:

            direction_text = (
                "🟡 <b>NEUTRAL / WATCH</b>"
            )

        # ------------------------------------------------------
        # Fusion
        # ------------------------------------------------------

        fusion = self._get_dict(
            signal.get("fusion")
        )

        # Prefer top-level values if present,
        # otherwise use fusion values.

        score = signal.get(
            "score",
            fusion.get("score", 0),
        )

        grade = signal.get(
            "grade",
            fusion.get("grade", "-"),
        )

        confluence = signal.get(
            "confluence",
            fusion.get("confluence", 0),
        )

        state = signal.get(
            "state",
            fusion.get("state", "-"),
        )

        # ------------------------------------------------------
        # Components
        # ------------------------------------------------------

        components = self._get_dict(
            signal.get(
                "components",
                fusion.get(
                    "components",
                    {},
                ),
            )
        )

        technical = components.get(
            "technical"
        )

        smc = components.get(
            "smc"
        )

        mtf = components.get(
            "mtf"
        )

        derivatives = components.get(
            "derivatives"
        )

        market = components.get(
            "market"
        )

        # ------------------------------------------------------
        # Trade plan
        # ------------------------------------------------------

        trade_plan = self._get_dict(
            signal.get(
                "trade_plan"
            )
        )

        entry = trade_plan.get(
            "entry"
        )

        stop_loss = trade_plan.get(
            "stop_loss"
        )

        tp1 = trade_plan.get(
            "tp1"
        )

        tp2 = trade_plan.get(
            "tp2"
        )

        tp3 = trade_plan.get(
            "tp3"
        )

        # Support alternative naming.

        if stop_loss is None:
            stop_loss = trade_plan.get(
                "sl"
            )

        # ------------------------------------------------------
        # Risk
        # ------------------------------------------------------

        risk = self._get_dict(
            signal.get(
                "risk"
            )
        )

        position = self._get_dict(
            risk.get(
                "position"
            )
        )

        leverage = self._get_dict(
            risk.get(
                "leverage"
            )
        )

        risk_percent = position.get(
            "risk_percent"
        )

        position_notional = position.get(
            "position_notional"
        )

        leverage_value = leverage.get(
            "leverage"
        )

        # Support alternative risk structures.

        if risk_percent is None:
            risk_percent = risk.get(
                "risk_percent"
            )

        if position_notional is None:
            position_notional = risk.get(
                "position_notional"
            )

        if leverage_value is None:
            leverage_value = risk.get(
                "leverage"
            )

        # ------------------------------------------------------
        # Gemini
        # ------------------------------------------------------

        gemini = self._get_dict(
            signal.get(
                "gemini"
            )
        )

        gemini_verdict = str(
            gemini.get(
                "verdict",
                gemini.get(
                    "decision",
                    "N/A",
                ),
            )
        ).upper()

        gemini_confidence = gemini.get(
            "confidence",
            0,
        )

        gemini_reason = self._safe_text(
            gemini.get(
                "reason",
                "",
            ),
            "",
        )

        # ------------------------------------------------------
        # Warnings
        # ------------------------------------------------------

        warnings = []

        fusion_warnings = fusion.get(
            "warnings",
            [],
        )

        signal_warnings = signal.get(
            "warnings",
            [],
        )

        gemini_risk_flags = gemini.get(
            "risk_flags",
            [],
        )

        for warning_list in (
            fusion_warnings,
            signal_warnings,
            gemini_risk_flags,
        ):

            if not isinstance(
                warning_list,
                list,
            ):
                continue

            for warning in warning_list:

                if warning is None:
                    continue

                warning_text = str(
                    warning
                ).strip()

                if warning_text:
                    warnings.append(
                        warning_text
                    )

        # Remove duplicates while preserving order.

        warnings = list(
            dict.fromkeys(
                warnings
            )
        )

        # ------------------------------------------------------
        # Build message
        # ------------------------------------------------------

        lines = [

            "🚨 <b>SMC CRYPTO SIGNAL</b>",
            "",
            f"🪙 <b>{symbol}</b>",
            direction_text,
            "",
            (
                f"⭐ Score: "
                f"<b>{self._safe_number(score)}/100</b>"
            ),
            (
                f"🏆 Grade: "
                f"<b>{self._safe_text(grade)}</b>"
            ),
            (
                f"🔥 Confluence: "
                f"<b>{self._safe_number(confluence)}%</b>"
            ),
            (
                f"📌 State: "
                f"<b>{self._safe_text(state)}</b>"
            ),
            "",
        ]

        # ------------------------------------------------------
        # Execution levels
        # ------------------------------------------------------

        if entry is not None:

            lines.extend(
                [
                    "📐 <b>Trade Plan</b>",
                    (
                        f"📍 Entry: "
                        f"<b>{self._safe_number(entry)}</b>"
                    ),
                    (
                        f"🛑 SL: "
                        f"<b>{self._safe_number(stop_loss)}</b>"
                    ),
                    (
                        f"🎯 TP1: "
                        f"<b>{self._safe_number(tp1)}</b>"
                    ),
                    (
                        f"🎯 TP2: "
                        f"<b>{self._safe_number(tp2)}</b>"
                    ),
                    (
                        f"🎯 TP3: "
                        f"<b>{self._safe_number(tp3)}</b>"
                    ),
                    "",
                ]
            )

        # ------------------------------------------------------
        # Analysis
        # ------------------------------------------------------

        lines.extend(
            [
                "📊 <b>Analysis</b>",
                (
                    f"Technical: "
                    f"{self._safe_number(technical)}"
                ),
                (
                    f"🧠 SMC: "
                    f"{self._safe_number(smc)}"
                ),
                (
                    f"⏱ MTF: "
                    f"{self._safe_number(mtf)}"
                ),
                (
                    f"📈 Derivatives: "
                    f"{self._safe_number(derivatives)}"
                ),
                (
                    f"🌐 Market: "
                    f"{self._safe_number(market)}"
                ),
                "",
            ]
        )

        # ------------------------------------------------------
        # Risk
        # ------------------------------------------------------

        if risk:

            lines.extend(
                [
                    "💰 <b>Risk</b>",
                    (
                        f"Risk: "
                        f"{self._safe_number(risk_percent)}%"
                    ),
                    (
                        f"Position: "
                        f"${self._safe_number(position_notional)}"
                    ),
                    (
                        f"Leverage: "
                        f"{self._safe_number(leverage_value)}x"
                    ),
                    "",
                ]
            )

        # ------------------------------------------------------
        # Gemini
        # ------------------------------------------------------

        lines.extend(
            [
                "🤖 <b>Gemini Review</b>",
                (
                    f"Verdict: "
                    f"<b>{self._safe_text(gemini_verdict)}</b>"
                ),
                (
                    f"Confidence: "
                    f"{self._safe_number(gemini_confidence)}%"
                ),
            ]
        )

        if gemini_reason:

            lines.append(
                f"Reason: {gemini_reason}"
            )

        # ------------------------------------------------------
        # Risk flags
        # ------------------------------------------------------

        if warnings:

            lines.extend(
                [
                    "",
                    "⚠️ <b>Risk Flags</b>",
                ]
            )

            for warning in warnings:

                lines.append(
                    "• "
                    + self._safe_text(
                        warning
                    )
                )

        # ------------------------------------------------------
        # Footer
        # ------------------------------------------------------

        lines.extend(
            [
                "",
                "⚠️ <i>Analysis only — "
                "not financial advice.</i>",
            ]
        )

        return "\n".join(
            lines
        )

    # ==========================================================
    # Send signal
    # ==========================================================

    def send_signal(
        self,
        signal: Dict[str, Any],
    ) -> Dict[str, Any]:

        try:

            message = self.format_signal(
                signal
            )

        except Exception as exc:

            logger.exception(
                "Telegram signal formatting failed: %s",
                exc,
            )

            return {
                "status": "FAILED",
                "reason": (
                    "Signal formatting failed"
                ),
                "error": str(exc),
            }

        return self.send_message(
            message
        )

    # ==========================================================
    # System message
    # ==========================================================

    def send_status(
        self,
        message: str,
    ) -> Dict[str, Any]:

        safe_message = self._safe_text(
            message,
            "",
        )

        text = (
            "🤖 <b>Crypto Signal Bot</b>\n\n"
            + safe_message
        )

        return self.send_message(
            text
        )
