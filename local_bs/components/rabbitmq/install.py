import json
from os.path import join

from ..service_names import RABBITMQ

from ... import constants
from ...config import config
from ...logger import get_logger

from ...utils.install import yum_install
from ...utils.systemd import systemd
from ...utils.logrotate import set_logrotate
from ...utils.deploy import deploy, copy_notice
from ...utils.common import sudo, mkdir, chown, remove
from ...utils.network import wait_for_port, is_port_open


LOG_DIR = join(constants.BASE_LOG_DIR, RABBITMQ)
HOME_DIR = join('/etc', RABBITMQ)
CONFIG_PATH = join(constants.COMPONENTS_DIR, RABBITMQ, 'config')

SECURE_PORT = 5671
INSECURE_PORT = 5672

logger = get_logger(RABBITMQ)


def _install_sources():
    sources = config[RABBITMQ]['sources']
    for source in sources.values():
        yum_install(source)


def _deploy_resources():
    deploy(
        src=join(CONFIG_PATH, 'rabbitmq_ulimit.conf'),
        dst='/etc/security/limits.d/rabbitmq.conf'
    )
    deploy(
        src=join(CONFIG_PATH, 'rabbitmq-definitions.json'),
        dst=join(HOME_DIR, 'definitions.json'),
        render=False
    )
    deploy(
        src=join(CONFIG_PATH, 'rabbitmq-env.conf'),
        dst=join(HOME_DIR, 'rabbitmq-env.conf')
    )
    chown('rabbitmq', 'rabbitmq', HOME_DIR)


def _enable_plugins():
    logger.info('Enabling RabbitMQ Plugins...')
    # Occasional timing issues with rabbitmq starting have resulted in
    # failures when first trying to enable plugins
    sudo(
        ['rabbitmq-plugins', 'enable', 'rabbitmq_management'],
        retries=5
    )
    sudo(
        ['rabbitmq-plugins', 'enable', 'rabbitmq_tracing'],
        retries=5
    )


def _init_service():
    logger.info('Initializing RabbitMQ...')
    rabbit_config_path = join(HOME_DIR, 'rabbitmq.config')

    # Delete old mnesia node
    remove('/var/lib/rabbitmq/mnesia')
    remove(rabbit_config_path)
    systemd.systemctl('daemon-reload')

    # rabbitmq restart exits with 143 status code that is valid in this case.
    systemd.restart(RABBITMQ, ignore_failure=True)
    wait_for_port(INSECURE_PORT)

    deploy(
        src=join(CONFIG_PATH, 'rabbitmq.config'),
        dst=rabbit_config_path,
        render=False
    )


def user_exists(username):
    output = sudo(['rabbitmqctl', 'list_users'], retries=5).aggr_stdout
    return username in output


def _delete_guest_user():
    if user_exists('guest'):
        logger.info('Disabling RabbitMQ guest user...')
        sudo(['rabbitmqctl', 'clear_permissions', 'guest'], retries=5)
        sudo(['rabbitmqctl', 'delete_user', 'guest'], retries=5)


def _create_rabbitmq_user():
    rabbitmq_username = config[RABBITMQ]['username']
    rabbitmq_password = config[RABBITMQ]['password']
    if not user_exists(rabbitmq_username):
        logger.info('Creating new user and setting permissions...'.format(
            rabbitmq_username, rabbitmq_password)
        )
        sudo(['rabbitmqctl', 'add_user', rabbitmq_username, rabbitmq_password])
        sudo(['rabbitmqctl', 'set_permissions',
              rabbitmq_username, '.*', '.*', '.*'], retries=5)
        sudo(['rabbitmqctl', 'set_user_tags', rabbitmq_username,
              'administrator'])


def _set_rabbitmq_policy(name, expression, policy):
    policy = json.dumps(policy)
    logger.debug('Setting policy {0} on queues {1} to {2}'.format(
        name, expression, policy))
    # shlex screws this up because we need to pass json and shlex
    # strips quotes so we explicitly pass it as a list.
    sudo(['rabbitmqctl', 'set_policy', name,
          expression, policy, '--apply-to', 'queues'])


def _set_policies():
    metrics = config[RABBITMQ]['policy_metrics']
    logs_queue_message_policy = {
        'message-ttl': metrics['logs_queue_message_ttl'],
        'max-length': metrics['logs_queue_length_limit']
    }
    events_queue_message_policy = {
        'message-ttl': metrics['events_queue_message_ttl'],
        'max-length': metrics['events_queue_length_limit']
    }
    metrics_queue_message_policy = {
        'message-ttl': metrics['metrics_queue_message_ttl'],
        'max-length': metrics['metrics_queue_length_limit']
    }
    riemann_deployment_queues_message_ttl = {
        'message-ttl': metrics['metrics_queue_message_ttl'],
        'max-length': metrics['metrics_queue_length_limit']
    }

    logger.info("Setting RabbitMQ Policies...")
    _set_rabbitmq_policy(
        name='logs_queue_message_policy',
        expression='^cloudify-logs$',
        policy=logs_queue_message_policy
    )
    _set_rabbitmq_policy(
        name='events_queue_message_policy',
        expression='^cloudify-events$',
        policy=events_queue_message_policy
    )
    _set_rabbitmq_policy(
        name='metrics_queue_message_policy',
        expression='^amq\.gen.*$',
        policy=metrics_queue_message_policy
    )
    _set_rabbitmq_policy(
        name='riemann_deployment_queues_message_ttl',
        expression='^.*-riemann$',
        policy=riemann_deployment_queues_message_ttl
    )


def _start_rabbitmq():
    logger.info("Starting RabbitMQ Service...")
    # rabbitmq restart exits with 143 status code that is valid in this case.
    systemd.restart(RABBITMQ, ignore_failure=True)
    wait_for_port(SECURE_PORT)
    _set_policies()
    systemd.restart(RABBITMQ)


def _validate_rabbitmq_running():
    logger.info('Making sure RabbitMQ is live...')
    systemd.verify_alive(RABBITMQ)

    result = sudo(['rabbitmqctl', 'status'])
    if result.returncode != 0:
        raise StandardError('Rabbitmq failed to start')

    if not is_port_open(SECURE_PORT, host='127.0.0.1'):
        raise StandardError(
            '{0} error: port {1}:{2} was not open'.format(
                RABBITMQ, '127.0.0.1', SECURE_PORT)
        )


def run():
    logger.info('Installing RabbitMQ...')
    copy_notice(RABBITMQ)
    mkdir(LOG_DIR)
    chown(RABBITMQ, RABBITMQ, LOG_DIR)

    _install_sources()
    set_logrotate(RABBITMQ)
    systemd.configure(RABBITMQ)
    _deploy_resources()
    _init_service()
    _enable_plugins()
    _delete_guest_user()
    _create_rabbitmq_user()
    _start_rabbitmq()
    _validate_rabbitmq_running()

    logger.info('RabbitMQ is up and running!')
