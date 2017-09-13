from .common import run, sudo
from .files import get_local_source_path

from ..logger import get_logger

logger = get_logger('yum')


class RpmPackageHandler(object):

    def __init__(self, source_path):
        self.source_path = source_path
        self.package_name = self.get_rpm_package_name()

    def remove_existing_rpm_package(self):
        """Removes any version that satisfies the package name of the given
        source path.
        """
        if self._is_package_installed(self.package_name):
            logger.debug(
                'Removing existing package sources for package '
                'with name: {0}'.format(self.package_name))
            sudo(['rpm', '--noscripts', '-e', self.package_name])

    @staticmethod
    def _is_package_installed(name):
        installed = run(['rpm', '-q', name], ignore_failures=True)
        if installed.returncode == 0:
            return True
        return False

    def is_rpm_installed(self):
        """Returns true if provided rpm is already installed.
        """
        src_query = run(['rpm', '-qp', self.source_path])
        source_name = src_query.aggr_stdout.rstrip('\n\r')

        return self._is_package_installed(source_name)

    def get_rpm_package_name(self):
        """Returns the package name according to the info provided in the
        source file.
        """
        split_index = ' : '
        package_details = {}
        package_details_query = run(['rpm', '-qpi', self.source_path])
        rows = package_details_query.aggr_stdout.split('\n')
        # split raw data according to the ' : ' index
        for row in rows:
            if split_index in row:
                first_columb_index = row.index(split_index)
                key = row[:first_columb_index].strip()
                value = row[first_columb_index + len(split_index):].strip()
                package_details[key] = value
        return package_details['Name']


def _yum_install(package, package_name=None):
    package_name = package_name or package
    logger.info('Installing {0}...'.format(package_name))
    sudo(['yum', 'install', '-y', package])


def _install_rpm(rpm_path):
    rpm_handler = RpmPackageHandler(rpm_path)
    logger.debug(
        'Checking whether {0} is already '
        'installed...'.format(rpm_handler.package_name)
    )
    if rpm_handler.is_rpm_installed():
        logger.debug(
            'Package {0} is already installed.'.format(
                rpm_handler.package_name
            )
        )
        return

    # removes any existing versions of the package that do not match
    # the provided package source version
    rpm_handler.remove_existing_rpm_package()
    _yum_install(rpm_path, package_name=rpm_handler.package_name)


def _install_yum_package(package_name):
    is_installed = run(
        ['yum', '-q', 'list', 'installed', package_name],
        ignore_failures=True
    )
    if is_installed.returncode == 0:
        logger.debug('Package {0} is already installed.'.format(
            package_name))
        return
    _yum_install(package=package_name)


def yum_install(source):
    """Installs a package using yum.

    yum supports installing from URL, path and the default yum repo
    configured within your image.
    you can specify one of the following:
    [yum install -y] mylocalfile.rpm
    [yum install -y] mypackagename

    If the source is a package name, it will check whether it is already
    installed. If it is, it will do nothing. It not, it will install it.

    If the source is a url to an rpm and the file doesn't already exist
    in a predesignated archives file path (${CLOUDIFY_SOURCES_PATH}/),
    it will download it. It will then use that file to check if the
    package is already installed. If it is, it will do nothing. If not,
    it will install it.

    NOTE: This will currently not take into considerations situations
    in which a file was partially downloaded. If a file is partially
    downloaded, a re-download will not take place and rather an
    installation will be attempted, which will obviously fail since
    the rpm file is incomplete.
    ALSO NOTE: you cannot provide `yum_install` with a space
    separated array of packages as you can with `yum install`. You must
    provide one package per invocation.
    """
    # source is a url or a local file name
    if source.endswith('.rpm'):
        local_path = get_local_source_path(source)
        _install_rpm(local_path)
    # source is the name of a yum-repo based package name
    else:
        _install_yum_package(package_name=source)


def yum_remove(package, ignore_failures=False):
    logger.info('yum removing {0}...'.format(package))
    try:
        sudo(['yum', 'remove', '-y', package])
    except BaseException:
        msg = 'Package `{0}` may not been removed successfully!'
        if not ignore_failures:
            logger.error(msg)
            raise
        logger.warn(msg)


def pip_install(source, venv='', constraints_file=None):
    log_message = 'Installing {0}'.format(source)

    pip_cmd = '{0}/bin/pip'.format(venv) if venv else 'pip'
    cmdline = [pip_cmd, 'install', source, '--upgrade']

    if venv:
        log_message += ' in virtualenv {0}'.format(venv)
    if constraints_file:
        cmdline.extend(['-c', constraints_file])
        log_message += ' using constraints file {0}'.format(constraints_file)

    logger.info(log_message)
    sudo(cmdline)
