import json
import logging
import os
from typing import Any, Dict, Optional

from google import genai


logger = logging.getLogger("crypto-signal-bot")


class GeminiReviewer:
    """
    Gemini-based independent reviewer.

    Gemini receives the quantitative analysis and returns:

        CONFIRM
        CAUTION
        REJECT

    It must NOT invent market data or create a setup
    that does not exist in the supplied analysis.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
    ):

        self.api_key = (
            api_key
            or os.getenv(
                "GEMINI_API_KEY"
            )
        )

        self.model = (
            model
            or os.getenv(
                "GEMINI_MODEL"
            )
            or "gemini-2.5-flash"
        )

        self.client = None

        if self.api_key:

            try:

                self.client = genai.Client(
                    api_key=self.api_key
                )

            except Exception as exc:

                logger.warning(
                    "Gemini client initialization failed: %s",
                    exc,
                )

    # ==========================================================
    # Prompt
    # ==========================================================

    def _build_prompt(
        self,
        analysis: Dict[str, Any],
    ) -> str:

        compact_data = json.dumps(
            analysis,
            indent=2,
            default=str,
        )

        return f"""
You are a crypto market analysis reviewer.

You are NOT the primary signal generator.

Your job is to independently review the quantitative
analysis supplied below.

Rules:

1. Do not invent market data.
2. Do not assume missing data is bullish or bearish.
3. Do not create an entry that is not supported by the data.
4. Do not automatically reject because one component disagrees.
5. Look for confluence across SMC, technical analysis,
   multi-timeframe structure, derivatives and market context.
6. Pay special attention to:
   - liquidity sweeps
   - BOS / CHoCH
   - FVG
   - order blocks
   - premium/discount
   - trend alignment
   - Open Interest
   - funding
   - liquidation
   - crowded positioning
7. If the setup is good but entry timing is imperfect,
   prefer CAUTION rather than REJECT.
8. If there is a major contradiction or obvious risk,
   use CAUTION or REJECT.
9. Never guarantee profit.
10. Return ONLY valid JSON.

Allowed verdicts:

CONFIRM
CAUTION
REJECT

Required JSON format:

{{
  "verdict": "CONFIRM",
  "confidence": 0,
  "reason": "short explanation",
  "risk_flags": [],
  "bullish_factors": [],
  "bearish_factors": []
}}

Quantitative analysis:

{compact_data}
"""

    # ==========================================================
    # Parse response
    # ==========================================================

    @staticmethod
    def _parse_response(
        text: str,
    ) -> Dict[str, Any]:

        text = (
            text
            .strip()
        )

        # Remove accidental markdown fences.
        if text.startswith(
            "```"
        ):

            text = (
                text
                .replace(
                    "```json",
                    "",
                )
                .replace(
                    "```",
                    "",
                )
                .strip()
            )

        try:

            data = json.loads(
                text
            )

        except json.JSONDecodeError:

            return {
                "verdict": "CAUTION",
                "confidence": 0,
                "reason": (
                    "Gemini returned "
                    "invalid JSON"
                ),
                "risk_flags": [
                    "AI_PARSE_ERROR"
                ],
                "bullish_factors": [],
                "bearish_factors": [],
            }

        verdict = str(
            data.get(
                "verdict",
                "CAUTION",
            )
        ).upper()

        if verdict not in {
            "CONFIRM",
            "CAUTION",
            "REJECT",
        }:

            verdict = "CAUTION"

        try:

            confidence = float(
                data.get(
                    "confidence",
                    0,
                )
            )

        except (
            TypeError,
            ValueError,
        ):

            confidence = 0

        return {
            "verdict": verdict,

            "confidence": max(
                0,
                min(
                    100,
                    confidence,
                ),
            ),

            "reason": str(
                data.get(
                    "reason",
                    "",
                )
            ),

            "risk_flags": (
                data.get(
                    "risk_flags",
                    [],
                )
                if isinstance(
                    data.get(
                        "risk_flags",
                        [],
                    ),
                    list,
                )
                else []
            ),

            "bullish_factors": (
                data.get(
                    "bullish_factors",
                    [],
                )
                if isinstance(
                    data.get(
                        "bullish_factors",
                        [],
                    ),
                    list,
                )
                else []
            ),

            "bearish_factors": (
                data.get(
                    "bearish_factors",
                    [],
                )
                if isinstance(
                    data.get(
                        "bearish_factors",
                        [],
                    ),
                    list,
                )
                else []
            ),
        }

    # ==========================================================
    # Review
    # ==========================================================

    def review(
        self,
        analysis: Dict[str, Any],
    ) -> Dict[str, Any]:

        if not self.client:

            return {
                "verdict": "CAUTION",
                "confidence": 0,
                "reason": (
                    "Gemini API key is not configured"
                ),
                "risk_flags": [
                    "GEMINI_UNAVAILABLE"
                ],
                "bullish_factors": [],
                "bearish_factors": [],
                "status": "SKIPPED",
            }

        prompt = self._build_prompt(
            analysis
        )

        try:

            response = (
                self.client.models.generate_content(
                    model=self.model,
                    contents=prompt,
                )
            )

            text = getattr(
                response,
                "text",
                "",
            )

            result = (
                self._parse_response(
                    text
                )
            )

            result["status"] = (
                "SUCCESS"
            )

            return result

        except Exception as exc:

            logger.exception(
                "Gemini review failed"
            )

            return {
                "verdict": "CAUTION",
                "confidence": 0,
                "reason": (
                    "Gemini request failed"
                ),
                "risk_flags": [
                    "GEMINI_REQUEST_ERROR"
                ],
                "bullish_factors": [],
                "bearish_factors": [],
                "status": "FAILED",
                "error": str(exc),
            }
