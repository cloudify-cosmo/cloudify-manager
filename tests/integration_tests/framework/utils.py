import logging
import os
import shutil
import subprocess
import tempfile
import zipfile
from base64 import b64encode
from contextlib import contextmanager

import requests

from cloudify.utils import setup_logger
from cloudify_rest_client import CloudifyClient
from integration_tests.framework.constants import INSERT_MOCK_LICENSE_QUERY
from integration_tests.tests import utils as test_utils
from integration_tests.tests.constants import MANAGER_PYTHON

logger = setup_logger('testenv.utils')


CommandAsListException = Exception('provide command as a list of string')


class TestEnvironment:
    address: str

    def ca_cert(self):
        raise NotImplementedError('should be implemented in child classes')

    def cleanup(self):
        raise NotImplementedError('should be implemented in child classes')

    def copy_file_from_manager(self, source, target):
        raise NotImplementedError('should be implemented in child classes')

    def copy_file_from_mgmtworker(self, source, target):
        raise NotImplementedError('should be implemented in child classes')

    def copy_file_to_manager(self, source, target, owner=None, mode=None):
        raise NotImplementedError('should be implemented in child classes')

    def copy_file_to_mgmtworker(self, source, target, owner=None, mode=None):
        raise NotImplementedError('should be implemented in child classes')

    def discover_manager_address(self):
        raise NotImplementedError('should be implemented in child classes')

    # FIXME combine both execute_on_… and execute_python_on_…

    def execute_on_manager(self, command, redirect_logs=False):
        return _execute_command(
            self._run_on_manager_base_cmd(),
            command,
            redirect_logs,
        )

    def execute_on_mgmtworker(self, command, redirect_logs=False):
        return _execute_command(
            self._run_on_mgmtworker_base_cmd(),
            command,
            redirect_logs,
        )

    def execute_python_on_manager(self, params):
        if not isinstance(params, list):
            raise CommandAsListException
        base_cmd = self._run_on_manager_base_cmd()
        return subprocess.check_output(
            base_cmd +
            [self.python_executable_location()] +
            params
        ).decode('utf-8')

    def execute_python_on_mgmtworker(self, params):
        if not isinstance(params, list):
            raise CommandAsListException
        base_cmd = self._run_on_mgmtworker_base_cmd()
        return subprocess.check_output(
            base_cmd +
            [self.python_executable_location()] +
            params
        ).decode('utf-8')

    def file_exists_on_manager(self, file_path):
        try:
            self.execute_on_manager(['test', '-e', file_path])
        except subprocess.CalledProcessError:
            return False

        return True

    def python_executable_location(self):
        raise NotImplementedError('should be implemented in child classes')

    def read_manager_file(self, file_path, no_strip=False):
        result = self.execute_on_manager(
            ['cat', file_path]
        )
        if not no_strip:
            result = result.strip()
        return result

    def rest_client(self, ca_cert):
        raise NotImplementedError('should be implemented in child classes')

    def run_on_manager(self, command):
        if not isinstance(command, list):
            raise CommandAsListException
        return subprocess.Popen(
            self._run_on_manager_base_cmd() + command
        )

    def run_python_on_manager(self, params):
        if not isinstance(params, list):
            raise CommandAsListException
        return subprocess.Popen(
            self._run_on_manager_base_cmd() +
            [self.python_executable_location()] +
            params
        )

    def _run_on_manager_base_cmd(self):
        raise NotImplementedError('should be implemented in child classes')

    def _run_on_mgmtworker_base_cmd(self):
        raise NotImplementedError('should be implemented in child classes')

    def prepare_reset_storage_script(self):
        reset_script = test_utils.get_resource('scripts/reset_storage.py')
        reset_mgmtworker = test_utils.get_resource(
            'scripts/reset_storage_mgmtworker.py')
        prepare = test_utils.get_resource('scripts/prepare_reset_storage.py')

        self.copy_file_to_manager(reset_script, '/tmp/reset_storage.py')
        self.copy_file_to_manager(prepare, '/tmp/prepare_reset_storage.py')
        self.copy_file_to_mgmtworker(
            reset_mgmtworker, '/tmp/reset_storage_mgmtworker.py')

        self.execute_python_on_manager([
            '/tmp/prepare_reset_storage.py',
            '--config',
            '/tmp/reset_storage_config.json'
        ])

    def reset_storage(self):
        logger.info('Resetting PostgreSQL DB')
        # reset the storage by calling a script on the manager, to access
        # localhost-only APIs (rabbitmq management api)
        self.execute_python_on_manager([
            '/tmp/reset_storage.py',
            '--config',
            '/tmp/reset_storage_config.json',
        ])
        self.execute_python_on_mgmtworker([
            '/tmp/reset_storage_mgmtworker.py'
        ])


class AllInOneEnvironment(TestEnvironment):
    container_id: str

    def __init__(self, container_id: str):
        self.container_id = container_id
        self.discover_manager_address()

    def ca_cert(self):
        return self.read_manager_file(
            '/etc/cloudify/ssl/cloudify_internal_ca_cert.pem'
        )

    def cleanup(self):
        subprocess.check_call(['docker', 'rm', '-f', self.container_id])

    def copy_file_from_manager(self, source, target):
        subprocess.check_call(
            ['docker', 'cp', f'{self.container_id}:{source}', target]
        )

    copy_file_from_mgmtworker = copy_file_from_manager

    def copy_file_to_manager(self, source, target, owner=None, mode=None):
        ret_val = subprocess.check_call(
            ['docker', 'cp', source, f'{self.container_id}:{target}']
        )
        if owner:
            self.execute_on_manager(['chown', owner, target])
        if mode:
            self.execute_on_manager(['chmod', mode, target])
        return ret_val

    copy_file_to_mgmtworker = copy_file_to_manager

    def discover_manager_address(self):
        self.address = subprocess.check_output(
            ['docker', 'inspect',
             '--format={{range .NetworkSettings.Networks}}'
             '{{.IPAddress}}{{end}}',
             self.container_id
             ]
        ).decode('utf-8').strip()

    def python_executable_location(self):
        return MANAGER_PYTHON

    def rest_client(self, ca_cert):
        client = test_utils.create_rest_client(
            host=self.address,
            rest_port=443,
            rest_protocol='https',
            cert_path=ca_cert
        )
        return client

    def _run_on_manager_base_cmd(self):
        return [
            'docker', 'exec', '-e', 'LC_ALL=en_US.UTF-8', self.container_id
        ]

    _run_on_mgmtworker_base_cmd = _run_on_manager_base_cmd


class DistributedEnvironment(TestEnvironment):
    k8s_namespace: str
    manager_pod: str
    mgmtworker_pod: str

    def __init__(self, k8s_namespace: str):
        self.k8s_namespace = k8s_namespace
        self.discover_pod_names()
        self.discover_manager_address()

    def ca_cert(self):
        ca_cert_template =\
            '{{ index .data "cloudify_internal_ca_cert.pem"|base64decode }}'
        return subprocess.check_output([
            'kubectl', 'get', 'secrets/cloudify-services-certs',
            '--output=template', f'--template={ca_cert_template}'
        ]).decode('utf-8')

    def cleanup(self):
        pass

    # FIXME combine these pairs …_to/from/on_…
    def copy_file_from_manager(self, source, target):
        return subprocess.check_call([
            'kubectl', 'cp', f'{self.manager_pod}:{source}',
            '-c', 'rest-service', target
        ])

    def copy_file_from_mgmtworker(self, source, target):
        return subprocess.check_call([
            'kubectl', 'cp', f'{self.mgmtworker_pod}:{source}',
            '-c', 'mgmtworker', target
        ])

    def copy_file_to_manager(self, source, target, owner=None, mode=None):
        return_value = subprocess.check_call([
            'kubectl', 'cp', source, f'{self.manager_pod}:{target}',
            '-c', 'rest-service'
        ])
        if owner:
            self.execute_on_manager(['chown', owner, target])
        if mode:
            self.execute_on_manager(['chmod', mode, target])
        return return_value

    def copy_file_to_mgmtworker(self, source, target, owner=None, mode=None):
        return_value = subprocess.check_call([
            'kubectl', 'cp', source, f'{self.mgmtworker_pod}:{target}',
            '-c', 'mgmtworker'
        ])
        if owner:
            self.execute_on_mgmtworker(['chown', owner, target])
        if mode:
            self.execute_on_mgmtworker(['chmod', mode, target])
        return return_value

    def discover_manager_address(self):
        hostname_template = '{{' +\
            '(index (index .items 0).status.loadBalancer.ingress 0)' +\
            '.hostname' +\
            '}}'
        self.address = subprocess.check_output([
            'kubectl', 'get', 'ingress',
            '--namespace', self.k8s_namespace,
            '--output', 'template', f'--template={hostname_template}',
            ]).decode('utf-8')

    def discover_pod_names(self):
        pod_names = subprocess.check_output(
            ['kubectl', 'get', 'pods',
             '--namespace', self.k8s_namespace,
             '--field-selector=status.phase=Running',
             '--no-headers', '--output=template',
             '--template={{range .items}}{{.metadata.name}}{{" "}}{{end}}']
        ).decode('utf-8').strip()
        for pod_name in pod_names.split(' '):
            if pod_name.startswith('rest-service-'):
                self.manager_pod = pod_name
            elif pod_name.startswith('mgmtworker-'):
                self.mgmtworker_pod = pod_name

    def python_executable_location(self):
        return '/usr/local/bin/python'

    def rest_client(self, _):
        client = test_utils.create_rest_client(
            host=self.address,
            rest_port=80,
            rest_protocol='http',
        )
        return client

    def _run_on_manager_base_cmd(self, container_name='rest-service'):
        cmd = ['kubectl', 'exec', self.manager_pod]
        if container_name:
            cmd += ['-c', container_name]
        return cmd + ['--']

    def _run_on_mgmtworker_base_cmd(self, container_name='mgmtworker'):
        cmd = ['kubectl', 'exec', self.mgmtworker_pod]
        if container_name:
            cmd += ['-c', container_name]
        return cmd + ['--']


def _execute_command(base_cmd, command, redirect_logs=False):
    if not isinstance(command, list):
        raise CommandAsListException
    if redirect_logs:
        return subprocess.run(base_cmd + command)
    return subprocess.check_output(base_cmd + command).decode('utf-8')


def create_auth_header(username=None, password=None, token=None, tenant=None):
    """Create a valid authentication header either from username/password or
    a token if any were provided; return an empty dict otherwise
    """
    headers = {}
    if username and password:
        credentials = b64encode(
            '{0}:{1}'.format(username, password).encode('utf-8')
        ).decode('ascii')
        headers = {
            'Authorization':
            'Basic ' + credentials
        }
    elif token:
        headers = {'Authentication-Token': token}
    if tenant:
        headers['Tenant'] = tenant
    return headers


def create_rest_client(host, **kwargs):
    # Doing it with kwargs instead of arguments with default values to allow
    # not passing args (which will then use the default values), or explicitly
    # passing None (or False) which will then be passed as-is to the Client

    username = kwargs.get('username', 'admin')
    password = kwargs.get('password', 'admin')
    tenant = kwargs.get('tenant', 'default_tenant')
    token = kwargs.get('token')
    rest_port = kwargs.get('rest_port', 443)
    rest_protocol = kwargs.get('rest_protocol',
                               'https' if rest_port == 443 else 'http')
    cert_path = kwargs.get('cert_path')
    trust_all = kwargs.get('trust_all', False)

    headers = create_auth_header(username, password, token, tenant)

    return CloudifyClient(
        host=host,
        port=rest_port,
        protocol=rest_protocol,
        headers=headers,
        trust_all=trust_all,
        cert=cert_path)


@contextmanager
def zip_files(files):
    source_folder = tempfile.mkdtemp()
    destination_zip = source_folder + '.zip'
    for path in files:
        shutil.copy(path, source_folder)
    create_zip(source_folder, destination_zip, include_folder=False)
    shutil.rmtree(source_folder)
    try:
        yield destination_zip
    finally:
        os.remove(destination_zip)


def unzip(archive, destination):
    with zipfile.ZipFile(archive, 'r') as zip_file:
        zip_file.extractall(destination)


def create_zip(source, destination, include_folder=True):
    with zipfile.ZipFile(destination, 'w') as zip_file:
        for root, _, files in os.walk(source):
            for filename in files:
                file_path = os.path.join(root, filename)
                source_dir = os.path.dirname(source) if include_folder \
                    else source
                zip_file.write(
                    file_path, os.path.relpath(file_path, source_dir))
    return destination


def download_file(file_url, tmp_file):
    logger.info('Retrieving file: {0}'.format(file_url))
    response = requests.get(file_url, stream=True)
    with open(tmp_file, "wb") as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)
    return tmp_file


def start_manager_container(
    image,
    resource_mapping=None,
    lightweight=False,
):
    manager_config = """
manager:
    security:
        admin_password: admin
        ssl_enabled: true
validations:
    skip_validations: true
sanity:
    skip_sanity: true
restservice:
    gunicorn:
        max_worker_count: 4
"""
    if lightweight:
        manager_config += """
stage:
    skip_installation: true
composer:
    skip_installation: true

# no monitoring
services_to_install:
- database_service
- queue_service
- manager_service
"""
    with tempfile.NamedTemporaryFile(delete=False, mode='w') as conf:
        conf.write(manager_config)
    command = [
        'docker', 'run', '-d',
        '-v', '{0}:/etc/cloudify/config.yaml'.format(conf.name),
    ]
    if resource_mapping:
        for src, dst in resource_mapping:
            command += ['-v', '{0}:{1}:ro'.format(src, dst)]
    command += [image]
    logging.info('Starting container: %s', ' '.join(command))
    container_id = subprocess.check_output(command).decode('utf-8').strip()
    logging.info('Started container %s', container_id)
    environment = AllInOneEnvironment(container_id)
    environment.execute_on_manager(
        ['cfy_manager', 'wait-for-starter'],
        redirect_logs=True,
    )
    return environment


def upload_mock_license(environment):
    environment.execute_on_manager([
        'sudo', '-u', 'postgres', 'psql', 'cloudify_db',
        '-c', INSERT_MOCK_LICENSE_QUERY,
    ])
