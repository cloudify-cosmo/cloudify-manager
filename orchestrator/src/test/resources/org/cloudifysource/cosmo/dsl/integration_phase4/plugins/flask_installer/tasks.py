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

from cosmo.celery import celery
import tempfile
import os
from os import path
import sys
import subprocess


@celery.task
def install(**kwargs):
    pass


@celery.task
def start(**kwargs):
    pass


@celery.task
def deploy_application(application_name, application_code, port=8080, **kwargs):
    application_path = path.join(tempfile.gettempdir(), 'flask-apps', application_name)
    os.makedirs(application_path)
    application_file = path.join(application_path, 'app.py')
    with open(application_file, "w") as f: f.write(application_code.replace("${port}", port))
    command = [sys.executable, application_file]
    subprocess.Popen(command)


def test():
    application_name = 'test-app'
    application_code = """
from flask import Flask
app = Flask(__name__)

@app.route("/")
def hello():
    return "Hello World!"

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=${port})
    """

    deploy_application(application_name, application_code, 8080)

