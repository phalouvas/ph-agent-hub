# =============================================================================
# PH Agent Hub — Anthropic Provider Client
# =============================================================================

from agent_framework import AnthropicChatClient

from ..db.orm.models import Model


def build_anthropic_client(model: Model) -> AnthropicChatClient:
    """Build an Anthropic chat client from a Model record.

    The model.api_key is already decrypted by the EncryptedString ORM type.
    """
    return AnthropicChatClient(
        api_key=model.api_key,
        base_url=model.base_url,
    )
