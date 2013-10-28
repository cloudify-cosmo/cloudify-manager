########
# Copyright (c) 2013 GigaSpaces Technologies Ltd. All rights reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
#    * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    * See the License for the specific language governing permissions and
#    * limitations under the License.

__author__ = 'idanmo'

from cosmo.celery import celery
import os
import subprocess
from celery.utils.log import get_task_logger
import threading
import Queue

COSMO_JAR = os.environ.get('COSMO_JAR')

logger = get_task_logger(__name__)
return_value = Queue.Queue()
thread_obj = None

class BackgroundProcess(threading.Thread):

    sp = None

    def __init__(self, dsl):
        self.dsl = dsl
        threading.Thread.__init__(self)

    def run(self):
        try:
            logger.info("deploying dsl: " + self.dsl)
            command = [
                "java",
                '-XX:MaxPermSize=256m',
                "-jar",
                COSMO_JAR,
                "--dsl",
                self.dsl,
                "--timeout",
                "300",
                "--non-interactive"
            ]
            self.sp = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            while True:
                line = self.sp.stdout.readline()
                if not line:
                    break
                logger.info(line.rstrip())
            self.sp.wait()
            if self.sp.returncode != 0:
                raise RuntimeError("Application Deployment failed with exit code {0}".format(self.sp.returncode))
            logger.info("dsl has been deployed [dsl={0}]".format(self.dsl))
            return_value.put(0)
        except Exception, e:
            return_value.put(e)

    def kill(self):
        logger.info("killing deploy process")
        self.sp.terminate()

@celery.task
def deploy(dsl, **kwargs):
    global thread_obj
    thread_obj = BackgroundProcess(dsl)
    thread_obj.start()

@celery.task
def get_deploy_return_value(**kwargs):
    r = None
    if not return_value.empty():
        r = return_value.get_nowait()
        if r is Exception:
            raise r

    return r

@celery.task
def kill(**kwargs):
    thread_obj.kill()