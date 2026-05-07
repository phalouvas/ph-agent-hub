# =============================================================================
# PH Agent Hub — DeepSeek Provider Client
# =============================================================================

from agent_framework.openai import OpenAIChatCompletionClient

from ..db.orm.models import Model


def build_deepseek_client(model: Model) -> OpenAIChatCompletionClient:
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
    return OpenAIChatCompletionClient(
        model=model.model_id or model.name,
        api_key=model.api_key,
        base_url=base_url,
    )
