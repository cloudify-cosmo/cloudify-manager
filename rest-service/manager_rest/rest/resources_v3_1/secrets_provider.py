from manager_rest.security import (
    MissingPremiumFeatureResource,
)

try:
    from cloudify_premium.secrets_provider.secured_secrets_provider_resource \
        import (
            SecuredSecretsProviderResource,
            SecuredSecretsProviderKeyResource,
        )
except ImportError:
    SecuredSecretsProviderResource = MissingPremiumFeatureResource
    SecuredSecretsProviderKeyResource = MissingPremiumFeatureResource


class SecretsProvider(SecuredSecretsProviderResource):
    pass


class SecretsProviderKey(SecuredSecretsProviderKeyResource):
    pass
