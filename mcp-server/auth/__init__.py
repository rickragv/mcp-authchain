"""Pluggable auth provider registry.

Selects auth provider based on settings.yaml `auth.provider` field.
Each provider module exposes `create_verifier(config) → Callable[[str], FirebaseUser]`.

To add a new provider:
  1. Create mcp-server/auth/my_provider.py with create_verifier(config)
  2. Add "my_provider" to PROVIDERS dict below
  3. Add config section in settings.yaml under auth.my_provider
  4. Set auth.provider: "my_provider"
"""

import importlib
import logging
from typing import Callable

from commons.types import FirebaseUser

log = logging.getLogger(__name__)

# Registry: provider name → module path
PROVIDERS: dict[str, str] = {
    "firebase": ".auth.firebase",
    "azure_ad": ".auth.azure_ad",
    "jwt": ".auth.jwt_generic",
}


def get_verifier(settings) -> Callable[[str], FirebaseUser]:
    """Load the configured auth provider and return its verify function.

    Returns a sync function: verify(token: str) → FirebaseUser
    """
    provider_name = settings.auth.provider

    if provider_name not in PROVIDERS:
        raise ValueError(
            f"Unknown auth provider: '{provider_name}'. "
            f"Available: {list(PROVIDERS.keys())}"
        )

    module_path = PROVIDERS[provider_name]
    module = importlib.import_module(module_path, package="mcp-server")

    provider_config = settings.auth.providers.get(provider_name, {})
    verifier = module.create_verifier(provider_config)

    log.info("auth.provider_loaded provider=%s", provider_name)
    return verifier
