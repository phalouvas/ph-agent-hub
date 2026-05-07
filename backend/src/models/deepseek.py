# =============================================================================
# PH Agent Hub — DeepSeek Provider Client
# =============================================================================

from agent_framework import OpenAIChatClient

from ..db.orm.models import Model


def build_deepseek_client(model: Model) -> OpenAIChatClient:
    """Build a DeepSeek chat client from a Model record.

    DeepSeek exposes an OpenAI-compatible API, so we use OpenAIChatClient
    with a custom base_url. Raises ValueError if base_url is not set.
    """
    if not model.base_url:
        raise ValueError("DeepSeek provider requires a base_url")
    return OpenAIChatClient(
        api_key=model.api_key,
        base_url=model.base_url,
    )
