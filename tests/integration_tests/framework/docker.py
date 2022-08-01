import shlex
import logging
import tempfile
import subprocess

from integration_tests.framework.constants import INSERT_MOCK_LICENSE_QUERY


def run_manager(
    image,
    service_management,
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
service_management: {0}
    """.format(service_management)
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
        '-v', '/sys/fs/cgroup:/sys/fs/cgroup:ro',
        '-v', '{0}:/etc/cloudify/config.yaml:Z'.format(conf.name),
        '--tmpfs', '/run', '--tmpfs', '/run/lock',
    ]
    if resource_mapping:
        for src, dst in resource_mapping:
            command += ['-v', '{0}:{1}:ro'.format(src, dst)]
    command += [image]
    logging.info('Starting container: %s', ' '.join(command))
    manager_id = subprocess.check_output(command).decode('utf-8').strip()
    logging.info('Started container %s', manager_id)
    execute(manager_id, ['cfy_manager', 'wait-for-starter'])
    return manager_id


def upload_mock_license(manager_id):
    execute(
        manager_id,
        'sudo -u postgres psql cloudify_db -c "{0}"'
        .format(INSERT_MOCK_LICENSE_QUERY)
    )


def clean(container_id):
    subprocess.check_call(['docker', 'rm', '-f', container_id])


def read_file(container_id, file_path, no_strip=False):
    result = subprocess.check_output([
        'docker', 'exec', container_id, 'cat', file_path
    ]).decode('utf-8')
    if not no_strip:
        result = result.strip()
    return result


def execute(container_id, command, env=None):
    if not isinstance(command, list):
        command = shlex.split(command)
    args = ['docker', 'exec']
    if not env:
        env = {}
    # assume utf-8 - for decoding the output, and so ask the executables
    # to use utf-8 indeed
    env.setdefault('LC_ALL', 'en_US.UTF-8')
    for k, v in env.items():
        args += ['-e', '{0}={1}'.format(k, v)]
    args.append(container_id)
    return subprocess.check_output(args + command).decode('utf-8')


def copy_file_to_manager(container_id, source, target):
    subprocess.check_call([
        'docker', 'cp', source, '{0}:{1}'.format(container_id, target)
    ])


def copy_file_from_manager(container_id, source, target):
    subprocess.check_call([
        'docker', 'cp', '{0}:{1}'.format(container_id, source), target
    ])


def get_manager_ip(container_id):
    return subprocess.check_output([
        'docker', 'inspect',
        '--format={{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}',
        container_id
    ]).decode('utf-8').strip()


def file_exists(container_id, file_path):
    try:
        execute(container_id, 'test -e {0}'.format(file_path))
    except subprocess.CalledProcessError:
        return False

    return True
