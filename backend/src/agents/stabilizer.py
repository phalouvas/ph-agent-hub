# =============================================================================
# PH Agent Hub — DeepSeek Stabilizer
# =============================================================================
# Implements the 6-step stabilisation pipeline for DeepSeek model output:
#
#   1. Strip reasoning tokens (<think> blocks)
#   2. Extract JSON block from mixed text
#   3. Repair malformed JSON
#   4. Validate tool calls against available tool names
#   5. Retry with corrective prompt if invalid
#   6. Normalise final output
#
# Primary entry point: ``stabilize()``
# =============================================================================

import json as _json
import logging
import re
from typing import Callable, Awaitable

from ..core.config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Regex patterns for JSON repair
# ---------------------------------------------------------------------------

_RE_TRAILING_COMMA = re.compile(r",(\s*[}\]])")
_RE_UNQUOTED_KEY = re.compile(
    r'(?<=\{|\s)([a-zA-Z_][a-zA-Z0-9_]*)\s*:', re.MULTILINE
)
_RE_SINGLE_QUOTED_KEY = re.compile(
    r"'([a-zA-Z_][a-zA-Z0-9_]*)'(\s*:)", re.MULTILINE
)
_RE_SINGLE_QUOTED_VALUE = re.compile(
    r":\s*'([^']*)'", re.MULTILINE
)


# ---------------------------------------------------------------------------
# Step 1: Strip reasoning
# ---------------------------------------------------------------------------


def strip_reasoning(text: str) -> str:
    """Remove reasoning blocks and preambles from DeepSeek output."""
    from .deepseek_patch import strip_reasoning as _strip
    return _strip(text)


# ---------------------------------------------------------------------------
# Step 2: Extract JSON
# ---------------------------------------------------------------------------


def extract_json(text: str) -> str:
    """Extract the first valid-ish JSON object/array from mixed text."""
    from .deepseek_patch import extract_json_block
    return extract_json_block(text)


# ---------------------------------------------------------------------------
# Step 3: Repair malformed JSON
# ---------------------------------------------------------------------------


def repair_json(text: str) -> str:
    """Attempt to repair common JSON issues in LLM output.

    Handles: trailing commas, unquoted keys, single-quoted keys/values,
    unbalanced braces.
    """
    # Remove trailing commas before } or ]
    text = _RE_TRAILING_COMMA.sub(r"\1", text)

    # Try json-repair library if available; otherwise use regex
    try:
        from json_repair import repair_json as _lib_repair
        return _lib_repair(text)
    except ImportError:
        pass

    # Quote unquoted keys:  key:  →  "key":
    # Match keys that look like identifiers and are followed by :
    def _quote_key(m: re.Match) -> str:
        kw = m.group(1)
        # Skip if already inside a string
        return f'"{kw}":'

    text = _RE_UNQUOTED_KEY.sub(_quote_key, text)

    # Fix single-quoted keys: 'key': → "key":
    text = _RE_SINGLE_QUOTED_KEY.sub(r'"\1"\2', text)

    # Fix single-quoted string values: 'value' → "value"
    text = _RE_SINGLE_QUOTED_VALUE.sub(r': "\1"', text)

    # Balance braces — add missing closing braces
    text = _balance_braces(text)

    return text


def _balance_braces(text: str) -> str:
    """Add missing closing braces/brackets."""
    open_counts: dict[str, int] = {"{": 0, "[": 0}
    close_map = {"{": "}", "[": "]"}

    for ch in text:
        if ch in open_counts:
            open_counts[ch] += 1
        elif ch == "}":
            open_counts["{"] -= 1
        elif ch == "]":
            open_counts["["] -= 1

    suffix = ""
    for open_ch, count in open_counts.items():
        if count > 0:
            suffix += close_map[open_ch] * count

    return text + suffix


# ---------------------------------------------------------------------------
# Step 4: Validate tool calls
# ---------------------------------------------------------------------------


def validate_tool_calls(
    parsed: dict | list,
    available_tool_names: list[str],
) -> tuple[bool, str | None]:
    """Check parsed output for valid tool calls.

    Returns:
        A tuple of ``(is_valid, error_message)``.
        ``error_message`` is None when valid.
    """
    # Handle list of tool calls
    items = parsed if isinstance(parsed, list) else [parsed]

    for item in items:
        if not isinstance(item, dict):
            continue
        tool_name = item.get("name") or item.get("tool") or item.get("function")
        if tool_name and isinstance(tool_name, str):
            if tool_name not in available_tool_names:
                return False, (
                    f"Unknown tool '{tool_name}'. "
                    f"Available tools: {', '.join(available_tool_names) or '(none)'}"
                )

    return True, None


# ---------------------------------------------------------------------------
# Step 5 + 6: Main stabilise pipeline
# ---------------------------------------------------------------------------


async def stabilize(
    raw_output: str,
    available_tool_names: list[str],
    retry_callback: Callable[[str], Awaitable[str]] | None = None,
    step_count: int = 0,
) -> str:
    """Run the full DeepSeek stabilisation pipeline.

    Args:
        raw_output: Raw text output from the DeepSeek model.
        available_tool_names: List of tool names available to the agent.
        retry_callback: Optional async function that re-invokes the model
            with a corrective system message.  Receives an error message
            string and returns the new raw output.
        step_count: Current agent step count (for loop protection).

    Returns:
        Cleaned, validated output string (may be JSON or plain text).
    """
    # Step 1: Strip reasoning tokens
    if settings.DEEPSEEK_STRIP_REASONING:
        text = strip_reasoning(raw_output)
    else:
        text = raw_output

    # Step 2: Extract JSON block
    if settings.DEEPSEEK_JSON_REPAIR:
        json_candidate = extract_json(text)
    else:
        json_candidate = text

    # Step 3: Repair JSON
    try:
        if settings.DEEPSEEK_JSON_REPAIR:
            repaired = repair_json(json_candidate)
        else:
            repaired = json_candidate
        parsed = _json.loads(repaired)
    except _json.JSONDecodeError:
        # Not valid JSON — treat as plain text response
        logger.debug("Output is not JSON; treating as plain text. Length=%d", len(text))
        return text.strip()

    # Step 4: Validate tool calls
    if settings.DEEPSEEK_VALIDATE_TOOL_CALLS and available_tool_names:
        is_valid, error = validate_tool_calls(parsed, available_tool_names)
        if not is_valid and retry_callback:
            # Step 5: Retry with corrective message
            for attempt in range(settings.DEEPSEEK_MAX_RETRIES):
                logger.warning(
                    "Tool validation failed (attempt %d/%d): %s",
                    attempt + 1,
                    settings.DEEPSEEK_MAX_RETRIES,
                    error,
                )
                corrective_prompt = (
                    f"Your previous response contained an invalid tool call: {error}\n"
                    "Please correct your response and use only the available tools."
                )
                try:
                    new_output = await retry_callback(corrective_prompt)
                    return await stabilize(
                        new_output,
                        available_tool_names,
                        retry_callback=None,  # Don't recurse further
                        step_count=step_count + 1,
                    )
                except Exception as exc:
                    logger.error("Retry attempt %d failed: %s", attempt + 1, exc)
                    if attempt >= settings.DEEPSEEK_MAX_RETRIES - 1:
                        break

            # Final fallback: return error as plain text
            fallback = (
                f"I encountered an issue with the tool call: {error}\n"
                "Please try again with a valid tool from the available list."
            )
            return fallback

        elif not is_valid:
            logger.warning("Tool validation failed (no retry callback): %s", error)
            return _json.dumps(parsed)  # Return as-is, let caller handle

    # Step 6: Normalise — return compact JSON
    if isinstance(parsed, (dict, list)):
        return _json.dumps(parsed, ensure_ascii=False)

    return text.strip()


# ---------------------------------------------------------------------------
# Convenience: stabilise a plain text response without tool validation
# ---------------------------------------------------------------------------


def stabilize_text(raw_output: str) -> str:
    """Strip reasoning from plain text output (no tool validation)."""
    if settings.DEEPSEEK_STRIP_REASONING:
        return strip_reasoning(raw_output)
    return raw_output
