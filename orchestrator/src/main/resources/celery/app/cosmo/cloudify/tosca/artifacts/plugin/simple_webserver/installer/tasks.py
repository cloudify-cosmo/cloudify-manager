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

"""
A celery task for starting a simple http server using python command via ssh.
The start task assumes the started machine would be a vagrant machine and therefore would be
accessible through ssh using vagrant's default credentials.
"""

from cosmo.celery import celery
import paramiko
import time
import urllib2


def get_machine_ip(cloudify_runtime):
    if not cloudify_runtime:
        raise ValueError('cannot get machine ip - cloudify_runtime is not set')

    for value in cloudify_runtime.values():
        if 'ip' in value:
            return value['ip']
    else:
        raise ValueError('cannot get machine ip - cloudify_runtime format error')


@celery.task
def install(**kwargs):
    pass


@celery.task
def start(port=8080, cloudify_runtime=None, **kwargs):

    ip = get_machine_ip(cloudify_runtime)

    print("Starting http server [ip={0}, port={1}]".format(ip, port))

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(ip, username='vagrant', password='vagrant')

    shell = ssh.invoke_shell()
    shell.setblocking(0)
    shell.settimeout(60)

    command = "nohup python -m SimpleHTTPServer {0} > /dev/null &\n".format(port)

    shell.send(command)

    # verify http server is up
    for attempt in range(10):
        try:
            response = urllib2.urlopen("http://{0}:{1}".format(ip, port))
            response.read()
            break
        except:
            time.sleep(1)
    else:
        raise RuntimeError("failed to start http server")


def test():
    port = 8000
    cloudify_runtime = {'vm': {'ip': '10.0.0.5'}}
    start(port, cloudify_runtime)
