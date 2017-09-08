from os.path import join, dirname as up

CLOUDIFY_USER = 'cfyuser'
CLOUDIFY_GROUP = 'cfyuser'
CLOUDIFY_HOME_DIR = '/etc/cloudify'
SUDOERS_INCLUDE_DIR = '/etc/sudoers.d'
CLOUDIFY_SUDOERS_FILE = join(SUDOERS_INCLUDE_DIR, CLOUDIFY_USER)

BASE_RESOURCES_PATH = '/opt/cloudify'
CLOUDIFY_SOURCES_PATH = join(BASE_RESOURCES_PATH, 'sources')
MANAGER_RESOURCES_HOME = '/opt/manager/resources'
AGENT_ARCHIVES_PATH = '{0}/packages/agents'.format(MANAGER_RESOURCES_HOME)

BASE_LOG_DIR = '/var/log/cloudify'

INTERNAL_REST_PORT = 53333

BASE_DIR = up(__file__)
COMPONENTS_DIR = join(BASE_DIR, 'components')
