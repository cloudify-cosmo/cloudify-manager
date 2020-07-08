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

import subprocess
import tempfile

from cloudify import ctx
from cloudify.decorators import operation


@operation
def start(ctx, **_):
    install_agent_script = ctx.agent.init_script({'user': 'cfyuser'})
    with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
        f.write(install_agent_script)
    subprocess.check_call(['bash', f.name])


@operation
def delete(**_):
    ctx.instance.runtime_properties.pop('ip', None)
