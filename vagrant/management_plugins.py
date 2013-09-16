#/*******************************************************************************
# * Copyright (c) 2013 GigaSpaces Technologies Ltd. All rights reserved
# *
# * Licensed under the Apache License, Version 2.0 (the "License");
# * you may not use this file except in compliance with the License.
# * You may obtain a copy of the License at
# *
# *       http://www.apache.org/licenses/LICENSE-2.0
# *
# * Unless required by applicable law or agreed to in writing, software
# * distributed under the License is distributed on an "AS IS" BASIS,
#    * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    * See the License for the specific language governing permissions and
#    * limitations under the License.
# *******************************************************************************/

__author__ = 'elip'

from versions import RIEMANN_LOADER_VERSION, VAGRANT_PROVISION_VERSION, WORKER_INSTALLER_VERSION

WORKER_INSTALLER = "https://github.com/CloudifySource/cosmo-plugin-agent-installer/archive/{0}.zip"\
                   .format(WORKER_INSTALLER_VERSION)
RIEMANN_LOADER = "https://github.com/CloudifySource/cosmo-plugin-riemann-configurer/archive/{0}.zip"\
                 .format(RIEMANN_LOADER_VERSION)
VAGRANT_PROVISION = "https://github.com/CloudifySource/cosmo-plugin-vagrant-provisioner/archive/{0}.zip"\
                    .format(VAGRANT_PROVISION_VERSION)

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
