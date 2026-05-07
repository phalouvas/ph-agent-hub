# =============================================================================
# PH Agent Hub — DeepSeek MAF Monkey-Patches
# =============================================================================
# All monkey-patches applied to MAF internals for DeepSeek compatibility
# are isolated here.  No other module modifies MAF internals.
#
# Call ``apply_deepseek_patches()`` once (it is idempotent) before running
# an agent with a DeepSeek model.
# =============================================================================

import logging
import re

logger = logging.getLogger(__name__)

_patched: bool = False


def apply_deepseek_patches() -> None:
    """Apply DeepSeek compatibility patches to MAF internals.

    Idempotent — calling multiple times is safe.
    """
    global _patched
    if _patched:
        return

    try:
        _patch_agent_framework()
        _patched = True
        logger.info("DeepSeek patches applied to agent-framework.")
    except Exception as exc:
        logger.warning("Failed to apply some DeepSeek patches: %s", exc)


# ---------------------------------------------------------------------------
# Patch helpers
# ---------------------------------------------------------------------------


def _patch_agent_framework() -> None:
    """Apply output-processing patches to the MAF agent-framework.

    We patch the OpenAIChatClient and/or Agent internals to handle
    DeepSeek-specific output quirks (reasoning blocks, malformed JSON, etc.).
    """
    try:
        from agent_framework.openai import OpenAIChatClient

        _patch_openai_chat_client(OpenAIChatClient)
    except ImportError:
        logger.warning("Could not import agent_framework.openai.OpenAIChatClient; skipping patches.")


def _patch_openai_chat_client(cls: type) -> None:
    """Monkey-patch OpenAIChatClient methods for DeepSeek compatibility."""

    # ---- Patch parse_output -----------------------------------------------
    _original_parse = getattr(cls, "parse_output", None)
    if _original_parse is not None:

        def patched_parse(self, output: str) -> str:
            # Strip reasoning before standard parse
            cleaned = strip_reasoning(output)
            return _original_parse(self, cleaned)

        cls.parse_output = patched_parse

    # ---- Patch extract_json ----------------------------------------------
    _original_extract_json = getattr(cls, "extract_json", None)
    if _original_extract_json is not None:

        def patched_extract_json(self, text: str) -> str:
            # Try standard extraction first
            try:
                return _original_extract_json(self, text)
            except Exception:
                # Fall back to our JSON extractor
                return extract_json_block(text)

        cls.extract_json = patched_extract_json


# ---------------------------------------------------------------------------
# Public utility functions (also used by stabilizer.py)
# ---------------------------------------------------------------------------

_RE_THINK = re.compile(
    r"<think[^>]*>.*?</think>", re.DOTALL | re.IGNORECASE
)
_RE_THINK_OPEN = re.compile(
    r"<think[^>]*>", re.IGNORECASE
)
_RE_THINK_CLOSE = re.compile(
    r"</think>", re.IGNORECASE
)


def strip_reasoning(text: str) -> str:
    """Remove DeepSeek ``<think>...</think>`` blocks and reasoning preamble.

    Also handles unclosed ``<think>`` tags by removing everything from the
    opening tag to the end of the text if no closing tag is found.
    """
    # Remove complete <think>...</think> blocks
    text = _RE_THINK.sub("", text)

    # If there's an unclosed <think>, remove from that point onward
    open_match = _RE_THINK_OPEN.search(text)
    close_match = _RE_THINK_CLOSE.search(text)
    if open_match and not close_match:
        text = text[: open_match.start()]

    # Remove leading whitespace/blanks
    text = text.strip()

    return text


def extract_json_block(text: str) -> str:
    """Extract a JSON object or array from mixed text.

    Tries to find the outermost ``{...}`` or ``[...]`` block in *text*.
    Returns the raw matched substring, or the original text if no JSON-like
    structure is found.
    """
    # Try to find the first { and matching }
    start = text.find("{")
    if start == -1:
        start = text.find("[")
    if start == -1:
        return text

    # Bracket matching
    bracket_map = {"{": "}", "[": "]"}
    open_char = text[start]
    close_char = bracket_map[open_char]
    depth = 0
    end = start

    for i in range(start, len(text)):
        ch = text[i]
        if ch == open_char:
            depth += 1
        elif ch == close_char:
            depth -= 1
            if depth == 0:
                end = i + 1
                break

    if depth == 0:
        return text[start:end]

    return text
