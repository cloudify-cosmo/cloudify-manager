########
# Copyright (c) 2018 Cloudify Platform Ltd. All rights reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from __future__ import absolute_import
import os
import time
import tarfile
from io import BytesIO

import docker
from docker.types import Mount

from integration_tests.resources.dockerfiles import agent_host


class DockerInterface(object):

    @staticmethod
    def get_docker_client(docker_base_url=None, docker_port='2375'):
        """Get a Docker Py client.
        docker.get_env does not work,
        because we do not specify the port in our DOCKER_HOST env variable.
        """
        docker_base_url = \
            docker_base_url or '{0}:{1}'.format(
                os.getenv('DOCKER_HOST'), docker_port)
        return docker.DockerClient(base_url=docker_base_url, version='auto')

    @property
    def docker_client(self):
        return self.get_docker_client()

    def list_image_tags(self):
        return [tag.encode('utf-8') for image in
                self.docker_client.images.list() for tag in image.tags]

    def pull_image(self, **kwargs):
        return self.docker_client.images.pull(**kwargs)

    def build_image(self, dockerfile, image_name, **kwargs):
        return self.docker_client.images.build(
            path=dockerfile, tag=image_name, **kwargs)

    def run_container(self, image_name, **kwargs):
        """Start building the wagon."""
        return self.docker_client.containers.run(image_name, **kwargs)

    def run_agent_container(self, hostname, manager_ip, logger):
        if 'agent_host:latest' not in self.list_image_tags():
            logger.info('Building docker image.')
            self.build_image(agent_host, 'agent_host', rm=True)
            logger.info('Finished Building...running.')
        try:
            container = self.run_container(
                'agent_host:latest',
                cap_add=['SYS_ADMIN'],
                name=hostname,
                hostname=hostname,
                detach=True,
                mounts=[
                    Mount(
                        '/run',
                        source='',
                        type='tmpfs'
                    ),
                    Mount(
                        '/run/lock',
                        source='',
                        type='tmpfs'
                    )
                ],
                volumes={
                    '/sys/fs/cgroup': {
                        'bind': '/sys/fs/cgroup',
                        'mode': 'ro',
                    }
                },
                environment={
                    'MANAGER': manager_ip,
                    'NODE_INSTANCE_ID': hostname
                },
                security_opt=['seccomp:unconfined']
            )
        except Exception as e:
            logger.error('Failed to run: {0}'.format(e.message))
            raise e
        container.exec_run('python /root/script.py', detach=True)
        return container

    def put_file_on_container(self, bits, target_path, container_id):
        target_container = self.docker_client.containers.get(container_id)
        target_container.put_archive(target_path, bits)

    def mkdirs_on_container(self, target_path, container_id):
        container = self.docker_client.containers.get(container_id)
        container.exec_run('mkdir -p {0}'.format(os.path.dirname(target_path)))

    def extract_tar_on_container(self,
                                 archive_path,
                                 output_path,
                                 container_id):
        container = self.docker_client.containers.get(container_id)
        container.exec_run(
            'tar -xzvf {0} --strip=1 -C {1}'.format(archive_path, output_path))

    def download_file_to_container(self,
                                   file_content,
                                   target_path,
                                   target_container_id):
        self.mkdirs_on_container(
            os.path.dirname(target_path), target_container_id)
        self.put_file_on_container(
            file_content, target_path, target_container_id)

    @staticmethod
    def tar_file_content_for_put_archive(content, filename):
        stream = BytesIO()
        t = tarfile.TarFile(fileobj=stream, mode='w')
        file_data = content.encode('utf-8')
        tarinfo = tarfile.TarInfo(name=filename)
        tarinfo.size = len(file_data)
        tarinfo.mtime = time.time()
        t.addfile(tarinfo, BytesIO(file_data))
        t.close()
        stream.seek(0)
        return stream

    @staticmethod
    def get_container_ip(container, retry_interval=1, max_retries=10):
        retry_number = 0
        while True:
            container.reload()
            retry_number += 1
            container_networks = container.attrs['NetworkSettings']['Networks']
            container_ip = \
                container_networks['bridge']['IPAddress'].encode('utf-8')
            if container_ip:
                return container_ip
            if retry_number == max_retries:
                return '127.0.0.1'
            time.sleep(retry_interval)
