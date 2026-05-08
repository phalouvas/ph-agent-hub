# =============================================================================
# PH Agent Hub — DeepSeek Provider Client
# =============================================================================

import json
import logging
from typing import Any, Mapping, Sequence

from agent_framework._types import Content, Message
from agent_framework.openai import OpenAIChatCompletionClient
from openai.types.chat import ChatCompletion, ChatCompletionChunk

from ..db.orm.models import Model

logger = logging.getLogger(__name__)


class DeepSeekThinkingClient(OpenAIChatCompletionClient):
    """OpenAI-compatible client with DeepSeek thinking mode support.

    When ``thinking_enabled=True``, adds ``extra_body={"thinking": {"type":
    "enabled"}}`` to every request.  Handles the ``reasoning_content``
    field in both non-streaming and streaming responses, converting it to
    ``Content`` items of type ``text_reasoning``.
    """

    def __init__(self, *args: Any, thinking_enabled: bool = False, **kwargs: Any) -> None:
        self._thinking_enabled = thinking_enabled
        super().__init__(*args, **kwargs)

    # ---- Overrides --------------------------------------------------------

    def _prepare_options(
        self,
        messages: Sequence[Message],
        options: Mapping[str, Any],
    ) -> dict[str, Any]:
        """Inject ``extra_body`` with explicit thinking mode (always sent).

        DeepSeek's default thinking behavior varies by model (some have it
        on by default).  We always send an explicit enabled/disabled to
        guarantee consistent behavior regardless of model defaults.
        """
        result = super()._prepare_options(messages, options)
        result["extra_body"] = {
            "thinking": {"type": "enabled" if self._thinking_enabled else "disabled"}
        }
        return result

    def _parse_response_from_openai(
        self,
        response: ChatCompletion,
        options: Mapping[str, Any],
    ) -> Any:  # ChatResponse
        """Extract ``reasoning_content`` from non-streaming response."""
        chat_response = super()._parse_response_from_openai(response, options)
        for choice in response.choices:
            rc = getattr(choice.message, "reasoning_content", None)
            if rc:
                chat_response.messages.contents.append(
                    Content.from_text_reasoning(
                        text=rc,
                        protected_data=json.dumps(rc),
                    )
                )
        return chat_response

    def _parse_response_update_from_openai(
        self,
        chunk: ChatCompletionChunk,
    ) -> Any:  # ChatResponseUpdate
        """Extract ``reasoning_content`` from streaming chunk."""
        update = super()._parse_response_update_from_openai(chunk)
        for choice in chunk.choices:
            rc_delta = getattr(choice.delta, "reasoning_content", None)
            if rc_delta:
                update.contents.append(
                    Content.from_text_reasoning(
                        text=rc_delta,
                        protected_data=json.dumps(rc_delta),
                    )
                )
        return update

    def _prepare_message_for_openai(
        self,
        message: Message,
    ) -> list[dict[str, Any]]:
        """Convert ``reasoning_details`` (protected_data) back to ``reasoning_content``."""
        prepared = super()._prepare_message_for_openai(message)
        for msg in prepared:
            if "reasoning_details" in msg:
                try:
                    msg["reasoning_content"] = json.loads(msg.pop("reasoning_details"))
                except (json.JSONDecodeError, TypeError):
                    logger.warning("Failed to decode reasoning_details for message")
        return prepared


# ---------------------------------------------------------------------------
# Builder
# ---------------------------------------------------------------------------


def build_deepseek_client(
    model: Model,
    thinking_enabled: bool = False,
) -> DeepSeekThinkingClient:
    """Build a DeepSeek chat client from a Model record.

    DeepSeek exposes an OpenAI-compatible Chat Completions API, so we use
    OpenAIChatCompletionClient with a custom base_url.
    Appends /v1 if not already present.
    Raises ValueError if base_url is not set.
    """
    if not model.base_url:
        raise ValueError("DeepSeek provider requires a base_url")
    base_url = model.base_url.rstrip("/")
    if not base_url.endswith("/v1"):
        base_url += "/v1"
    return DeepSeekThinkingClient(
        model=model.model_id or model.name,
        api_key=model.api_key,
        base_url=base_url,
        thinking_enabled=thinking_enabled,
    )
