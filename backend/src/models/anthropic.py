# =============================================================================
# PH Agent Hub — Anthropic Provider Client
# =============================================================================

from agent_framework.anthropic import AnthropicClient

from ..db.orm.models import Model


def build_anthropic_client(model: Model) -> AnthropicClient:
    """Build an Anthropic chat client from a Model record.

    The model.api_key is already decrypted by the EncryptedString ORM type.
    """
    return AnthropicClient(
        model=model.name,
        api_key=model.api_key,
        base_url=model.base_url,
    )
