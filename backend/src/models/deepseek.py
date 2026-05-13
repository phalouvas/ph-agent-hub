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
        """Inject ``extra_body`` with explicit thinking mode.

        When thinking is enabled but a tool call has just completed
        (tool result present in messages), disable thinking for this
        request to avoid the DeepSeek requirement that reasoning_content
        must be passed back — which MAF doesn't fully support across
        tool-call boundaries.
        """
        result = super()._prepare_options(messages, options)

        thinking_type = "disabled"
        if self._thinking_enabled:
            # Check if there are tool results in the conversation
            prepared_msgs = result.get("messages", [])
            has_tool_result = any(
                msg.get("role") == "tool" for msg in prepared_msgs
            )
            if not has_tool_result:
                thinking_type = "enabled"

        result["extra_body"] = {
            "thinking": {"type": thinking_type}
        }
        return result

    def _parse_response_from_openai(
        self,
        response: ChatCompletion,
        options: Mapping[str, Any],
    ) -> Any:  # ChatResponse
        """Extract ``reasoning_content`` and stabilise tool calls from DeepSeek response.

        DeepSeek models sometimes output tool calls as text markers
        (``🔧 function_name``) instead of proper OpenAI tool_calls.
        The stabiliser extracts these and injects them as proper
        function call objects that MAF can process.
        """
        # ---- Stabiliser: detect & inject tool calls from text content ----
        from ..agents.stabilizer import (
            strip_reasoning,
            extract_json,
            repair_json,
        )
        from ..agents.deepseek_patch import extract_json_block

        for choice in response.choices:
            msg = choice.message
            content = msg.content or ""
            # Only intervene when there are no native tool_calls AND the
            # content looks like it contains tool-call syntax.
            if (
                not msg.tool_calls
                and content
                and ("🔧" in content or "```json" in content or '"name"' in content)
            ):
                # Step 1: strip reasoning traces
                cleaned = strip_reasoning(content)

                # Step 2: try to extract JSON tool call blocks
                json_block = extract_json_block(cleaned)
                if json_block and json_block != cleaned:
                    try:
                        repaired = repair_json(json_block)
                        import json as _json
                        parsed = _json.loads(repaired)

                        # Wrap single tool call into list form
                        tool_calls_list = parsed if isinstance(parsed, list) else [parsed]
                        if isinstance(tool_calls_list, list) and tool_calls_list:
                            # Inject tool calls into the OpenAI response message
                            from openai.types.chat import (
                                ChatCompletionMessageToolCall,
                            )
                            from openai.types.chat.chat_completion_message_tool_call import Function

                            injected: list = []
                            for tc in tool_calls_list:
                                if not isinstance(tc, dict):
                                    continue
                                fn_name = tc.get("name") or tc.get("function") or tc.get("tool", "")
                                fn_args = tc.get("arguments") or tc.get("input") or {}
                                if not fn_name:
                                    continue
                                if isinstance(fn_args, dict):
                                    fn_args = _json.dumps(fn_args)
                                injected.append(
                                    ChatCompletionMessageToolCall(
                                        id=f"call_deepseek_{len(injected)}",
                                        function=Function(
                                            name=str(fn_name),
                                            arguments=str(fn_args),
                                        ),
                                        type="function",
                                    )
                                )

                            if injected:
                                # Build a new message with injected tool_calls
                                msg.tool_calls = injected
                                msg.content = cleaned  # preserve cleaned text
                                logger.info(
                                    "Stabiliser injected %d tool call(s) from DeepSeek text response",
                                    len(injected),
                                )
                    except Exception:
                        logger.debug(
                            "Stabiliser could not extract JSON tool calls from response",
                            exc_info=True,
                        )

        # ---- Original reasoning_content extraction ----
        chat_response = super()._parse_response_from_openai(response, options)
        for choice, msg in zip(response.choices, chat_response.messages):
            rc = getattr(choice.message, "reasoning_content", None)
            if rc:
                msg.contents.append(
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
        """Convert ``reasoning_details`` back to ``reasoning_content``.

        The base class may already decode ``reasoning_details`` from JSON
        (e.g. when it came from Content items).  We handle both cases.
        """
        prepared = super()._prepare_message_for_openai(message)
        for msg in prepared:
            if "reasoning_details" in msg:
                value = msg.pop("reasoning_details")
                if isinstance(value, str):
                    try:
                        msg["reasoning_content"] = json.loads(value)
                    except (json.JSONDecodeError, TypeError):
                        # Already a plain string from the base class decode
                        msg["reasoning_content"] = value
                else:
                    msg["reasoning_content"] = value
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

    # Pre-configure an AsyncOpenAI client with timeout and retry settings
    # to survive transient network errors during long multi-tool streaming runs.
    import openai

    openai_client = openai.AsyncOpenAI(
        api_key=model.api_key,
        base_url=base_url,
        max_retries=2,
        timeout=300.0,
    )

    return DeepSeekThinkingClient(
        model=model.model_id or model.name,
        async_client=openai_client,
        thinking_enabled=thinking_enabled,
    )
