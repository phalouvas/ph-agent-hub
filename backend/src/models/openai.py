# =============================================================================
# PH Agent Hub — OpenAI Provider Client
# =============================================================================

from agent_framework import OpenAIChatClient

from ..db.orm.models import Model


def build_openai_client(model: Model) -> OpenAIChatClient:
    """Build an OpenAI chat client from a Model record.

    The model.api_key is already decrypted by the EncryptedString ORM type.
    """
    return OpenAIChatClient(
        api_key=model.api_key,
        base_url=model.base_url,
    )
