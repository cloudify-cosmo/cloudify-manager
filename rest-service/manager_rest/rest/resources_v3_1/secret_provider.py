from typing import Any

from manager_rest.security import (
    MissingPremiumFeatureResource,
)

SecretProviderResource: Any

try:
    from cloudify_premium.secret_provider.secured_secret_provider_resource \
        import SecuredSecretProviderResource
except ImportError:
    SecuredSecretProviderResource = MissingPremiumFeatureResource


class SecretProvider(SecuredSecretProviderResource):
    pass
