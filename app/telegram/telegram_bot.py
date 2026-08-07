import logging
import os
from typing import Any, Dict, Optional

import requests


logger = logging.getLogger("crypto-signal-bot")


class TelegramBot:
    """
    Telegram notification service.

    Responsibilities:
        - Send formatted signal
        - Send system/status messages
        - Never calculate signals
    """

    def __init__(
        self,
        bot_token: Optional[str] = None,
        chat_id: Optional[str] = None,
        timeout: int = 10,
    ):

        self.bot_token = (
            bot_token
            or os.getenv(
                "TELEGRAM_BOT_TOKEN"
            )
        )

        self.chat_id = (
            chat_id
            or os.getenv(
                "TELEGRAM_CHAT_ID"
            )
        )

        self.timeout = timeout

        self.base_url = (
            "https://api.telegram.org"
        )

    # ==========================================================
    # Basic validation
    # ==========================================================

    @property
    def configured(self) -> bool:

        return bool(
            self.bot_token
            and self.chat_id
        )

    # ==========================================================
    # Send message
    # ==========================================================

    def send_message(
        self,
        text: str,
        disable_web_page_preview: bool = True,
    ) -> Dict[str, Any]:

        if not self.configured:

            return {
                "status": "SKIPPED",
                "reason": (
                    "Telegram credentials not configured"
                ),
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

            return {
                "status": "FAILED",
                "reason": data.get(
                    "description",
                    "Telegram API error",
                ),
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

    # ==========================================================
    # Signal formatter
    # ==========================================================

    def format_signal(
        self,
        signal: Dict[str, Any],
    ) -> str:

        symbol = signal.get(
            "symbol",
            "UNKNOWN",
        )

        direction = str(
            signal.get(
                "direction",
                "WATCH",
            )
        ).upper()

        score = signal.get(
            "score",
            0,
        )

        grade = signal.get(
            "grade",
            "-",
        )

        confluence = signal.get(
            "confluence",
            0,
        )

        # ------------------------------------------------------
        # Direction emoji
        # ------------------------------------------------------

        if direction == "LONG":

            direction_text = (
                "🟢 LONG"
            )

        elif direction == "SHORT":

            direction_text = (
                "🔴 SHORT"
            )

        else:

            direction_text = (
                "🟡 WATCH"
            )

        # ------------------------------------------------------
        # Trade plan
        # ------------------------------------------------------

        trade_plan = signal.get(
            "trade_plan",
            {},
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

        # ------------------------------------------------------
        # Components
        # ------------------------------------------------------

        components = signal.get(
            "components",
            {},
        )

        technical = components.get(
            "technical",
            0,
        )

        smc = components.get(
            "smc",
            0,
        )

        mtf = components.get(
            "mtf",
            0,
        )

        derivatives = components.get(
            "derivatives",
            0,
        )

        market = components.get(
            "market",
            0,
        )

        # ------------------------------------------------------
        # Risk
        # ------------------------------------------------------

        risk = signal.get(
            "risk",
            {},
        )

        position = risk.get(
            "position",
            {},
        )

        leverage = risk.get(
            "leverage",
            {},
        )

        risk_percent = position.get(
            "risk_percent"
        )

        position_notional = (
            position.get(
                "position_notional"
            )
        )

        leverage_value = (
            leverage.get(
                "leverage"
            )
        )

        # ------------------------------------------------------
        # Gemini
        # ------------------------------------------------------

        gemini = signal.get(
            "gemini",
            {},
        )

        gemini_verdict = gemini.get(
            "verdict",
            "N/A",
        )

        gemini_confidence = (
            gemini.get(
                "confidence",
                0,
            )
        )

        gemini_reason = gemini.get(
            "reason",
            "",
        )

        # ------------------------------------------------------
        # Warnings
        # ------------------------------------------------------

        warnings = []

        warnings.extend(
            signal.get(
                "warnings",
                [],
            )
        )

        warnings.extend(
            gemini.get(
                "risk_flags",
                [],
            )
        )

        # Remove duplicates.

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
            f"⭐ Score: <b>{score}/100</b>",
            f"🏆 Grade: <b>{grade}</b>",
            (
                f"🔥 Confluence: "
                f"<b>{confluence}%</b>"
            ),
            "",
        ]

        # Only show execution levels
        # when available.

        if entry is not None:

            lines.extend(
                [
                    f"📍 Entry: <b>{entry}</b>",
                    (
                        f"🛑 SL: "
                        f"<b>{stop_loss}</b>"
                    ),
                    "",
                    (
                        f"🎯 TP1: "
                        f"<b>{tp1}</b>"
                    ),
                    (
                        f"🎯 TP2: "
                        f"<b>{tp2}</b>"
                    ),
                    (
                        f"🎯 TP3: "
                        f"<b>{tp3}</b>"
                    ),
                    "",
                ]
            )

        lines.extend(
            [
                "📊 <b>Analysis</b>",
                (
                    f"Technical: "
                    f"{technical}"
                ),
                f"🧠 SMC: {smc}",
                f"⏱ MTF: {mtf}",
                (
                    f"📈 Derivatives: "
                    f"{derivatives}"
                ),
                f"🌐 Market: {market}",
                "",
            ]
        )

        if risk:

            lines.extend(
                [
                    "💰 <b>Risk</b>",
                    (
                        f"Risk: "
                        f"{risk_percent}%"
                    ),
                    (
                        f"Position: "
                        f"${position_notional}"
                    ),
                    (
                        f"Leverage: "
                        f"{leverage_value}x"
                    ),
                    "",
                ]
            )

        lines.extend(
            [
                "🤖 <b>Gemini Review</b>",
                (
                    f"Verdict: "
                    f"<b>{gemini_verdict}</b>"
                ),
                (
                    f"Confidence: "
                    f"{gemini_confidence}%"
                ),
            ]
        )

        if gemini_reason:

            lines.append(
                f"Reason: {gemini_reason}"
            )

        if warnings:

            lines.extend(
                [
                    "",
                    "⚠️ <b>Risk Flags</b>",
                ]
            )

            for warning in warnings:

                lines.append(
                    f"• {warning}"
                )

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

        message = (
            self.format_signal(
                signal
            )
        )

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

        text = (
            "🤖 <b>Crypto Signal Bot</b>\n\n"
            + message
        )

        return self.send_message(
            text
        )
