########
# Copyright (c) 2016 GigaSpaces Technologies Ltd. All rights reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os

import sh

from integration_tests import docl


RIEMANN_CONFIGS_DIR = '/opt/riemann'


def is_riemann_core_up(deployment_id):
    core_indicator = os.path.join(RIEMANN_CONFIGS_DIR, deployment_id, 'ok')
    try:
        out = docl.read_file(core_indicator)
        return out == 'ok'
    except sh.ErrorReturnCode:
        return False


def reset_data_and_restart():
    docl.execute('rm -rf {0}'.format(RIEMANN_CONFIGS_DIR))
    docl.execute('mkdir -p {0}'.format(RIEMANN_CONFIGS_DIR))
    docl.execute('systemctl restart cloudify-riemann')
