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

import urllib2
import os
from os import path
import errno
import tempfile
import sys
import subprocess

from cosmo.events import send_event

from cosmo.celery import celery


@celery.task
def start(__relationship_cloudify_id, **kwargs):
    send_event(__relationship_cloudify_id, "10.0.0.5", "flask app status", "state", "running")


@celery.task
def deploy(application_name, application_url, port=8080, **kwargs):
    response = urllib2.urlopen(application_url)
    application_path = path.join(tempfile.gettempdir(), 'flask-apps', application_name)

    try:
        os.makedirs(application_path)
    except OSError as e:
        if not (e.errno == errno.EEXIST):
            raise

    application_file = path.join(application_path, 'app.py')
    with open(application_file, "w") as f:
        f.write(response.read())

    command = [sys.executable, application_file, str(port)]
    subprocess.Popen(command)
