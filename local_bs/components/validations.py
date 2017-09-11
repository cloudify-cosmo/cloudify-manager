import sys
import urllib2
import platform
import subprocess

from .service_names import VALIDATIONS, MANAGER

from ..config import config
from ..logger import get_logger

from ..utils.network import is_url

logger = get_logger(VALIDATIONS)

_errors = []


def _get_os_distro():
    distro, version, _ = \
        platform.linux_distribution(full_distribution_name=False)
    return distro.lower(), version.split('.')[0]


def _get_host_total_memory():
    """
    MemTotal:        7854400 kB
    MemFree:         1811840 kB
    MemAvailable:    3250176 kB
    Buffers:          171164 kB
    Cached:          1558216 kB
    SwapCached:       119180 kB
    """
    with open('/proc/meminfo') as memfile:
        memory = memfile.read()
    for attribute in memory.splitlines():
        if attribute.lower().startswith('memtotal'):
            return int(attribute.split(':')[1].strip().split(' ')[0]) / 1024


def _get_available_host_disk_space():
    """
    Filesystem                 Type 1G-blocks  Used Available Use% Mounted on
    /dev/mapper/my_file_system ext4      213G   63G      139G  32% /
    """
    df = subprocess.Popen(["df", "-BG", "/etc/issue"], stdout=subprocess.PIPE)
    output = df.communicate()[0]
    available_disk_space_in_gb = output.split("\n")[1].split()[3].rstrip('G')
    return int(available_disk_space_in_gb)


def _validate_supported_distros():
    logger.info('Validating supported distributions...')
    distro, version = _get_os_distro()
    supported_distros = config[VALIDATIONS]['supported_distros']
    supported_distro_versions = \
        config[VALIDATIONS]['supported_distro_versions']
    if distro not in supported_distros:
        _errors.append(
            'Cloudify manager does not support the current distro (`{0}`),'
            'supported distros are: {1}'.format(distro, supported_distros)
        )
    if version not in supported_distro_versions:
        _errors.append(
            'Cloudify manager does not support the current distro version '
            '(`{0}`), supported versions are: {1}'.format(
                version, supported_distro_versions
            )
        )


def _validate_python_version():
    logger.info('Validating Python version...')
    major_version, minor_version = sys.version_info[0], sys.version_info[1]
    python_version = '{0}.{1}'.format(major_version, minor_version)
    expected_version = config[VALIDATIONS]['expected_python_version']
    if python_version != expected_version:
        error = 'Local python version (`{0}`) does not match expected ' \
                'version (`{1}`)'.format(python_version, expected_version)
        _errors.append(error)


def _validate_sufficient_memory():
    logger.info('Validating memory requirement...')
    current_memory = _get_host_total_memory()
    required_memory = \
        config[VALIDATIONS]['minimum_required_total_physical_memory_in_mb']
    if current_memory < required_memory:
        _errors.append(
            'The provided host does not have enough memory to run '
            'Cloudify Manager (Current: {0}MB, Required: {1}MB).'.format(
                current_memory, required_memory)
        )


def _validate_sufficient_disk_space():
    logger.info('Validating disk space requirement...')
    available_disk_space_in_gb = _get_available_host_disk_space()
    required_disk_space = \
        config[VALIDATIONS]['minimum_required_available_disk_space_in_gb']

    if available_disk_space_in_gb < required_disk_space:
        _errors.append(
            'The provided host does not have enough disk space to run '
            'Cloudify Manager (Current: {0}GB, Required: {1}GB).'.format(
                available_disk_space_in_gb, required_disk_space)
        )


def _validate_resources_package_url():
    single_tar_url = config[MANAGER]['source']['manager_resources_package']
    if not single_tar_url or not is_url(single_tar_url):
        return
    try:
        urllib2.urlopen(single_tar_url)
    except urllib2.HTTPError as ex:
        _errors.append(
            "The Manager's Resources Package {0} is "
            "not accessible (HTTP Error: {1})".format(
                single_tar_url, ex.code))
    except urllib2.URLError as ex:
        _errors.append(
            "The Manager's Resources Package {0} is "
            "invalid (URL Error: {1})".format(
                single_tar_url, ex.args))


def validate_machine():
    if config[VALIDATIONS]['ignore_bootstrap_validations']:
        logger.info('Skipping validations')
        return

    logger.info('Validating local machine')
    _validate_python_version()
    _validate_supported_distros()
    _validate_sufficient_memory()
    _validate_sufficient_disk_space()
    _validate_resources_package_url()

    if _errors:
        printable_error = 'Validation error(s):\n' \
                          '{0}'.format('\n'.join(_errors))
        raise StandardError(printable_error)
    logger.info('All validations passed successfully!')
