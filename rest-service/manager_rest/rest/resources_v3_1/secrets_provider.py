from manager_rest.security import (
    MissingPremiumFeatureResource,
)

try:
    from cloudify_premium.secrets_provider.secured_secrets_provider_resource \
        import SecuredSecretsProviderResource
except ImportError:
    SecuredSecretsProviderResource = MissingPremiumFeatureResource


class SecretsProvider(SecuredSecretsProviderResource):
    pass
