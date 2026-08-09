import json
import logging
import os
from typing import Any, Dict, List, Optional

from google import genai
from google.genai import types


logger = logging.getLogger("crypto-signal-bot")


class GeminiReviewer:
    """
    Production Gemini-based independent reviewer.

    Gemini is a REVIEWER, not the primary signal generator.

    Input:
        Quantitative analysis produced by the system.

    Output:
        CONFIRM
        CAUTION
        REJECT

    Important design rules:
        - Gemini must not invent market data.
        - Gemini must not create a setup that does not exist.
        - Missing data must remain missing.
        - Gemini cannot override quantitative evidence.
        - Gemini does not determine the primary market direction.
        - Gemini is intentionally separated from directional confluence.
    """

    ALLOWED_VERDICTS = {
        "CONFIRM",
        "CAUTION",
        "REJECT",
    }

    DEFAULT_MODEL = "gemini-1.5-flash"

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
    ) -> None:

        self.api_key = (
            api_key
            or os.getenv("GEMINI_API_KEY")
        )

        self.model = (
            model
            or os.getenv("GEMINI_MODEL")
            or self.DEFAULT_MODEL
        )

        self.client = None

        if not self.api_key:

            logger.warning(
                "⚠️ GEMINI_API_KEY is not configured."
            )

            return

        try:

            self.client = genai.Client(
                api_key=self.api_key
            )

            logger.info(
                "✅ Gemini client initialized | model=%s",
                self.model,
            )

        except Exception as exc:

            logger.exception(
                "❌ Gemini client initialization failed: %s",
                exc,
            )

            self.client = None

    # ==========================================================
    # Default Result
    # ==========================================================

    @staticmethod
    def _unavailable_result(
        reason: str,
        status: str,
        risk_flag: str,
        error: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Safe fallback.

        IMPORTANT:
        Gemini failure must NEVER become CONFIRM.
        """

        result = {
            "verdict": "CAUTION",
            "decision": "CAUTION",
            "confidence": 0.0,
            "reason": reason,
            "risk_flags": [risk_flag],
            "bullish_factors": [],
            "bearish_factors": [],
            "status": status,
        }

        if error:
            result["error"] = error

        return result

    # ==========================================================
    # Prompt
    # ==========================================================

    def _build_prompt(
        self,
        analysis: Dict[str, Any],
    ) -> str:
        """
        Build a strict reviewer prompt.

        Gemini receives evidence only.
        It is not allowed to generate missing evidence.
        """

        compact_data = json.dumps(
            analysis,
            separators=(",", ":"),
            ensure_ascii=False,
            default=str,
        )

        return f"""
You are an independent reviewer inside a quantitative
cryptocurrency trading-analysis system.

You are NOT the primary signal generator.

Your ONLY task is to review the supplied analysis and classify
the QUALITY and RISK of the existing setup.

============================================================
STRICT DATA RULES
============================================================

1. Use ONLY information contained in the supplied analysis.

2. NEVER invent:
   - price
   - volume
   - Open Interest
   - funding rate
   - liquidation data
   - FVG
   - Order Block
   - BOS
   - CHoCH
   - liquidity sweep
   - support
   - resistance
   - entry
   - stop loss
   - take profit
   - market trend

3. If information is missing, treat it as UNKNOWN.

4. UNKNOWN is NOT bullish.

5. UNKNOWN is NOT bearish.

6. Do not create a trading setup from your own knowledge.

7. Do not use external/current market knowledge.

8. Do not assume that a coin will rise or fall.

============================================================
REVIEW PRIORITY
============================================================

Evaluate the supplied evidence in this order:

A. Overall quantitative direction
B. Technical trend
C. SMC structure
D. Liquidity sweep
E. BOS / CHoCH
F. Displacement
G. FVG
H. Order Block
I. Premium / Discount
J. Multi-timeframe alignment
K. Derivatives
L. Funding
M. Open Interest
N. Liquidation / crowded positioning
O. Market context
P. Existing risk warnings

============================================================
VERDICT RULES
============================================================

CONFIRM:
Use only when the supplied evidence shows strong and coherent
confluence and there is no major contradiction.

CAUTION:
Use when:
- the setup has meaningful evidence but timing is imperfect,
- some modules disagree,
- important information is missing,
- or there is elevated risk.

REJECT:
Use when:
- the supplied evidence contains a major contradiction,
- the setup is clearly invalid,
- or the risk is materially inconsistent with the proposed direction.

IMPORTANT:
Do NOT reject merely because one component disagrees.

============================================================
AI ROLE
============================================================

You are a reviewer.

You must NOT:
- create a better setup,
- invent an entry,
- invent a price target,
- override the quantitative engine,
- claim certainty,
- guarantee profit.

Your confidence represents ONLY your confidence in the REVIEW
of the supplied evidence.

It does NOT represent probability of profit.

============================================================
OUTPUT
============================================================

Return ONLY JSON matching the supplied schema.

The reason must be short and evidence-based.

Risk flags should contain only risks actually visible in the
supplied analysis.

Bullish factors should contain only supplied bullish evidence.

Bearish factors should contain only supplied bearish evidence.

============================================================
QUANTITATIVE ANALYSIS
============================================================

{compact_data}
"""

    # ==========================================================
    # Parse Response
    # ==========================================================

    @classmethod
    def _parse_response(
        cls,
        text: str,
    ) -> Dict[str, Any]:
        """
        Safely parse Gemini JSON.

        Handles accidental markdown fences and malformed
        responses without ever returning CONFIRM by default.
        """

        if not isinstance(text, str):

            return cls._unavailable_result(
                reason="Gemini returned no usable text",
                status="PARSE_ERROR",
                risk_flag="AI_PARSE_ERROR",
            )

        text = text.strip()

        if not text:

            return cls._unavailable_result(
                reason="Gemini returned an empty response",
                status="PARSE_ERROR",
                risk_flag="AI_EMPTY_RESPONSE",
            )

        # ------------------------------------------------------
        # Remove markdown code fences
        # ------------------------------------------------------

        if text.startswith("```"):

            lines = text.splitlines()

            if lines:
                lines = lines[1:]

            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]

            text = "\n".join(lines).strip()

        # ------------------------------------------------------
        # JSON parsing
        # ------------------------------------------------------

        try:

            data = json.loads(text)

        except json.JSONDecodeError:

            # Attempt to recover a JSON object if the model
            # surrounded it with accidental text.

            start = text.find("{")
            end = text.rfind("}")

            if start == -1 or end <= start:

                return cls._unavailable_result(
                    reason="Gemini returned invalid JSON",
                    status="PARSE_ERROR",
                    risk_flag="AI_PARSE_ERROR",
                )

            try:

                data = json.loads(
                    text[start:end + 1]
                )

            except json.JSONDecodeError:

                return cls._unavailable_result(
                    reason="Gemini returned invalid JSON",
                    status="PARSE_ERROR",
                    risk_flag="AI_PARSE_ERROR",
                )

        if not isinstance(data, dict):

            return cls._unavailable_result(
                reason="Gemini response was not a JSON object",
                status="PARSE_ERROR",
                risk_flag="AI_SCHEMA_ERROR",
            )

        # ======================================================
        # Verdict
        # ======================================================

        verdict = str(
            data.get(
                "verdict",
                "CAUTION",
            )
        ).upper().strip()

        if verdict not in cls.ALLOWED_VERDICTS:

            verdict = "CAUTION"

        # ======================================================
        # Decision Mapping
        # ======================================================

        if verdict == "CONFIRM":

            decision = "APPROVE"

        elif verdict == "REJECT":

            decision = "REJECT"

        else:

            decision = "CAUTION"

        # ======================================================
        # Confidence
        # ======================================================

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

            confidence = 0.0

        confidence = max(
            0.0,
            min(
                100.0,
                confidence,
            ),
        )

        # ======================================================
        # Safe list extraction
        # ======================================================

        def safe_list(
            key: str,
        ) -> List[str]:

            value = data.get(
                key,
                [],
            )

            if not isinstance(
                value,
                list,
            ):

                return []

            result = []

            for item in value:

                if item is None:
                    continue

                text_value = str(
                    item
                ).strip()

                if text_value:
                    result.append(
                        text_value
                    )

            return result

        reason = str(
            data.get(
                "reason",
                "",
            )
        ).strip()

        if not reason:

            reason = (
                "Gemini provided no detailed reason."
            )

        return {
            "verdict": verdict,
            "decision": decision,
            "confidence": confidence,
            "reason": reason,
            "risk_flags": safe_list(
                "risk_flags"
            ),
            "bullish_factors": safe_list(
                "bullish_factors"
            ),
            "bearish_factors": safe_list(
                "bearish_factors"
            ),
            "status": "SUCCESS",
        }

    # ==========================================================
    # JSON Schema
    # ==========================================================

    @staticmethod
    def _response_schema() -> Dict[str, Any]:
        """
        Structured output schema.

        Gemini's current GenAI SDK supports JSON structured
        output using response_mime_type and response_schema.
        """

        return {
            "type": "OBJECT",
            "properties": {
                "verdict": {
                    "type": "STRING",
                    "enum": [
                        "CONFIRM",
                        "CAUTION",
                        "REJECT",
                    ],
                },
                "confidence": {
                    "type": "NUMBER",
                },
                "reason": {
                    "type": "STRING",
                },
                "risk_flags": {
                    "type": "ARRAY",
                    "items": {
                        "type": "STRING",
                    },
                },
                "bullish_factors": {
                    "type": "ARRAY",
                    "items": {
                        "type": "STRING",
                    },
                },
                "bearish_factors": {
                    "type": "ARRAY",
                    "items": {
                        "type": "STRING",
                    },
                },
            },
            "required": [
                "verdict",
                "confidence",
                "reason",
                "risk_flags",
                "bullish_factors",
                "bearish_factors",
            ],
        }

    # ==========================================================
    # Review
    # ==========================================================

    def review(
        self,
        analysis: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Send quantitative analysis to Gemini.

        Gemini failure is fail-safe:
            CAUTION
        never:
            CONFIRM
        """

        if not isinstance(
            analysis,
            dict,
        ):

            return self._unavailable_result(
                reason="Invalid analysis supplied to Gemini",
                status="INVALID_INPUT",
                risk_flag="AI_INVALID_INPUT",
            )

        if not self.client:

            return self._unavailable_result(
                reason=(
                    "Gemini API client is unavailable"
                ),
                status="SKIPPED",
                risk_flag="GEMINI_UNAVAILABLE",
            )

        prompt = self._build_prompt(
            analysis
        )

        try:

            response = (
                self.client.models.generate_content(
                    model=self.model,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        response_mime_type=(
                            "application/json"
                        ),
                        response_schema=(
                            self._response_schema()
                        ),
                        temperature=0.1,
                    ),
                )
            )

            text = getattr(
                response,
                "text",
                "",
            )

            result = self._parse_response(
                text
            )

            logger.info(
                (
                    "Gemini review | "
                    "verdict=%s | "
                    "confidence=%.1f | "
                    "status=%s"
                ),
                result.get("verdict"),
                result.get("confidence", 0),
                result.get("status"),
            )

            return result

        except Exception as exc:

            logger.exception(
                "❌ Gemini review failed"
            )

            return self._unavailable_result(
                reason="Gemini request failed",
                status="FAILED",
                risk_flag="GEMINI_REQUEST_ERROR",
                error=str(exc),
            )
