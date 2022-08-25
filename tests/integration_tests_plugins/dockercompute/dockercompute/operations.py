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
import shutil
import subprocess
import tempfile

from cloudify import ctx
from cloudify.decorators import operation
from cloudify.exceptions import NonRecoverableError


@operation
def start(ctx, **_):
    install_agent_script = ctx.agent.init_script(
        {
            'user': 'cfyuser',
            'basedir': '/etc/cloudify'
        }
    )
    with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
        f.write(install_agent_script)

    # daemonize the script, so that we're not a child of the mgmtworker,
    # so the agent is not killed when the mgmtworker dies
    if os.fork() == 0:
        os.chdir('/')
        os.setsid()
        os.umask(0)
        if os.fork() == 0:
            os.execv('/usr/bin/bash', ['/usr/bin/bash', f.name])


@operation
def store_envdir(ctx, **_):
    try:
        envdir = ctx.instance.runtime_properties['cloudify_agent']['envdir']
    except KeyError:
        envdir = None
    ctx.instance.runtime_properties['envdir'] = envdir


@operation
def delete(**_):
    envdir = ctx.instance.runtime_properties['envdir']
    if not envdir:
        return
    daemon_delete_cmd = [
        os.path.join(envdir, 'bin', 'cfy-agent'),
        'daemons', 'delete', '--name', ctx.instance.id
    ]
    subprocess.check_call(daemon_delete_cmd,
                          env={'CLOUDIFY_DAEMON_STORAGE_DIRECTORY':
                               os.path.expanduser('~cfyuser/.cfy-agent/')})

    shutil.rmtree(os.path.expanduser('~cfyuser/{0}'.format(ctx.instance.id)))
    ctx.instance.runtime_properties.pop('ip', None)


@operation
def fail_on_scale(ctx, **_):
    if ctx.workflow_id == 'scale':
        raise NonRecoverableError("fail!")
