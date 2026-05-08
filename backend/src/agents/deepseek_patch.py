# =============================================================================
# PH Agent Hub — DeepSeek Utility Functions
# =============================================================================
# Lightweight utilities for DeepSeek output processing.
# No longer monkey-patches MAF internals — thinking mode is handled by
# DeepSeekThinkingClient (see src/models/deepseek.py).
#
# Kept: strip_reasoning, extract_json_block (used by stabilizer.py)
# =============================================================================

import re

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
