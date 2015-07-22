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

import os
import shutil
import subprocess
import sys
import time
from os import path

import pika

from cloudify.celery import celery as celery_client
from cloudify.utils import setup_logger

from testenv.constants import FILE_SERVER_PORT
from testenv.constants import MANAGER_REST_PORT
from testenv.constants import FILE_SERVER_BLUEPRINTS_FOLDER


logger = setup_logger('celery_worker_process')


class CeleryWorkerProcess(object):

    def __init__(self,
                 queues,
                 test_working_dir,
                 additional_includes=None,
                 name=None,
                 hostname=None,
                 manager_rest_port=MANAGER_REST_PORT,
                 concurrency=1):

        self.test_working_dir = test_working_dir
        self.name = name or queues[0]
        self.hostname = hostname or queues[0]
        self.manager_rest_port = manager_rest_port
        self.queues = ','.join(queues)
        self.hostname = hostname or queues[0]
        self.concurrency = concurrency
        self.additional_includes = additional_includes or []
        self.riemann_config_dir = path.join(self.test_working_dir, 'riemann')

        # work folder for this worker
        self.workdir = os.path.join(
            self.test_working_dir,
            self.name,
            'work'
        )

        # env folder for this worker
        self.envdir = os.path.join(
            self.test_working_dir,
            self.name,
            'env'
        )
        self.celery_pid_file = path.join(self.workdir,
                                         'celery-{0}.pid'.format(self.name))
        self.celery_log_file = path.join(self.workdir,
                                         'celery-{0}.log'.format(self.name))

    def create_dirs(self):
        if not os.path.exists(self.workdir):
            os.makedirs(self.workdir)
        if not os.path.exists(self.envdir):
            os.makedirs(self.envdir)

    def delete_dirs(self):
        if os.path.exists(self.workdir):
            shutil.rmtree(self.workdir)
        if os.path.exists(self.envdir):
            shutil.rmtree(self.envdir)

    def start(self):

        _delete_amqp_queues(self.name, self.queues.split(','))

        self.create_dirs()

        # includes should always have
        # the initial includes configuration.
        includes = self._build_includes()
        includes.extend(self.additional_includes)

        python_path = sys.executable

        celery_command = [
            '{0}/celery'.format(path.dirname(python_path)),
            'worker',
            '-Ofair',
            '--events',
            '--loglevel=debug',
            '--hostname={0}'.format(self.hostname),
            '--purge',
            '--app=cloudify_agent.app.app',
            '--logfile={0}'.format(self.celery_log_file),
            '--pidfile={0}'.format(self.celery_pid_file),
            '--queues={0}'.format(self.queues),
            '--autoscale={0},1'.format(self.concurrency),
            '--include={0}'.format(','.join(includes))
        ]

        env_conf = dict(
            CELERY_QUEUES=self.queues,
            RIEMANN_CONFIGS_DIR=self.riemann_config_dir,
            CELERY_WORK_DIR=self.workdir,
            TEST_WORKING_DIR=self.test_working_dir,
            ENV_DIR=self.envdir,
            MANAGER_REST_PORT=str(self.manager_rest_port),
            MANAGEMENT_IP='localhost',
            MANAGER_FILE_SERVER_BLUEPRINTS_ROOT_URL='http://localhost:{0}/{1}'
            .format(FILE_SERVER_PORT, FILE_SERVER_BLUEPRINTS_FOLDER),
            MANAGER_FILE_SERVER_URL='http://localhost:{0}'
            .format(FILE_SERVER_PORT),
            AGENT_IP='localhost',
            VIRTUALENV=path.dirname(path.dirname(python_path))
        )

        environment = os.environ.copy()
        environment.update(env_conf)

        logger.info('Starting worker {0}. [command={1} | env={2} '
                    '| cwd={3}] | process_mode={4}'
                    .format(self.name,
                            celery_command,
                            env_conf,
                            self.envdir,
                            bool(os.environ.get('PROCESS_MODE'))))

        subprocess.Popen(celery_command,
                         env=environment,
                         cwd=self.envdir)

        timeout = 60
        worker_name = 'celery@{0}'.format(self.name)
        inspect = celery_client.control.inspect(destination=[worker_name])
        end_time = time.time() + timeout
        while time.time() < end_time:
            try:
                stats = (inspect.stats() or {}).get(worker_name)
                if stats:
                    pids = self._get_celery_process_ids()
                    logger.info('Celery worker {0} started [pids={1}]'
                                .format(self.name, pids))
                    return
                time.sleep(0.5)
            except BaseException as e:
                logger.warning('Error when inspecting celery : {0}'
                               .format(e.message))
                logger.warning('Retrying...')
                time.sleep(0.5)
        celery_log = self.try_read_logfile()
        if celery_log:
            celery_log = celery_log[len(celery_log) - 100000:]
            logger.error('Celery log ({0}):\n {1}'.format(
                self.celery_log_file, celery_log))
        self.stop()
        raise RuntimeError('Failed starting worker {0}. '
                           'waited for {1} seconds.'
                           .format(self.name, timeout))

    def restart(self):
        self.stop()
        self.start()

    def stop(self):
        pids = self._get_celery_process_ids()
        logger.info('Shutting down Celery worker {0} [pids={1}]'
                    .format(self.name, pids))
        os.system('kill -9 {0}'.format(' '.join(pids)))
        time.sleep(0.5)

    def _get_celery_process_ids(self):
        from subprocess import CalledProcessError
        try:
            grep = "ps aux | grep 'celery.*{0}' | grep -v grep".format(
                self.celery_pid_file)
            grep += " | awk '{print $2}'"
            output = subprocess.check_output(grep, shell=True)
            ids = filter(lambda x: len(x) > 0, output.split(os.linesep))
            return ids
        except CalledProcessError:
            return []

    def try_read_logfile(self):
        if path.exists(self.celery_log_file):
            with open(self.celery_log_file, 'r') as f:
                return f.read()
        return None

    def _build_includes(self):

        includes = [
            # this module will apply various monkey-patches
            # to the process.
            'testenv.mocks',
        ]

        for root, _, filenames in os.walk(self.envdir):
            for filename in filenames:
                file_path = os.path.join(root, filename)
                if '__init__' in file_path:
                    continue
                if 'pyc' in file_path:
                    continue
                module = os.path.splitext(file_path)[0].replace(
                    self.envdir, '').strip('/').replace('/', '.')
                includes.append(module)

        return includes


# copied from worker_installer/tasks.py:_delete_amqp_queues
def _delete_amqp_queues(worker_name, queues):
    connection = pika.BlockingConnection(
        pika.ConnectionParameters(host='localhost'))
    try:
        channel = connection.channel()
        for queue in queues:
            channel.queue_delete(queue)
        channel.queue_delete('celery@{0}.celery.pidbox'.format(worker_name))
    finally:
        try:
            connection.close()
        except Exception:
            pass
