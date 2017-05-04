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

from integration_tests.framework import docl
from integration_tests.framework.constants import CLOUDIFY_USER


RIEMANN_CONFIGS_DIR = '/opt/riemann'


def reset_data_and_restart():
    docl.execute('rm -rf {0}'.format(RIEMANN_CONFIGS_DIR))
    docl.execute('mkdir -p {0}'.format(RIEMANN_CONFIGS_DIR))
    # This is how the dir is currently set up during the bootstrap
    docl.execute('chown -R riemann:{0} {1}'.format(CLOUDIFY_USER,
                                                   RIEMANN_CONFIGS_DIR))
    docl.execute('chmod 770 {0}'.format(RIEMANN_CONFIGS_DIR))
    docl.execute('systemctl restart cloudify-riemann')
