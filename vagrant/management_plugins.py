import os

__author__ = 'elip'

DEFAULT_BRANCH = "feature/CLOUDIFY-2022-initial-commit"

BRANCH = os.environ.get("COSMO_BRANCH", DEFAULT_BRANCH)

WORKER_INSTALLER = "https://github.com/CloudifySource/cosmo-plugin-agent-installer/archive/{0}.zip".format(BRANCH)
RIEMANN_LOADER = "https://github.com/CloudifySource/cosmo-plugin-riemann-configurer/archive/{0}.zip".format(BRANCH)
VAGRANT_PROVISION = "https://github.com/CloudifySource/cosmo-plugin-vagrant-provisioner/archive/{0}.zip".format(BRANCH)

plugins = [

    {
        "name": "cloudify.tosca.artifacts.plugin.riemann_config_loader",
        "url": RIEMANN_LOADER

    },
    {
        "name": "cloudify.tosca.artifacts.plugin.worker_installer",
        "url": WORKER_INSTALLER
    },
    {
        "name": "cloudify.tosca.artifacts.plugin.vagrant_host_provisioner",
        "url": VAGRANT_PROVISION
    },
]
