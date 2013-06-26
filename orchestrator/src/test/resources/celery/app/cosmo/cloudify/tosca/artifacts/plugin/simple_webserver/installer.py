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
    if cloudify_runtime is None:
        raise ValueError('cannot get machine ip - cloudify_runtime is not set')
    try:
        for key in cloudify_runtime:
            return cloudify_runtime[key]['ip']
    except:
        pass
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

    attempts = 0
    max_attempts = 10
    http_server_running = False

    # verify http server is up
    while not http_server_running:
        try:
            response = urllib2.urlopen("http://{0}:{1}".format(ip, port))
            response.read()
            http_server_running = True
        except:
            attempts += 1
            if attempts > max_attempts:
                raise RuntimeError("failed to start http server")
            time.sleep(1)


def test():
    port = 8000
    vm = dict([('ip', '10.0.0.5')])
    cloudify_runtime = dict([('vm', vm)])
    start(port, cloudify_runtime)
