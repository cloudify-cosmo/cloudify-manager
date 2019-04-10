#########
# Copyright (c) 2019 Cloudify Platform Ltd. All rights reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
#  * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  * See the License for the specific language governing permissions and
#  * limitations under the License.
#

import platform
import subprocess
import pkg_resources
from manager_rest import premium_enabled


def get_version():
    return pkg_resources.get_distribution('cloudify-rest-service').version


def get_edition():
    return 'premium' if premium_enabled else 'community'


def get_distribution():
    distribution, _, release = platform.linux_distribution(
        full_distribution_name=False)
    return distribution, release


def get_version_data():
    version = get_version()
    distro, distro_release = get_distribution()
    if not premium_enabled:
        try:
            rpm_info = subprocess.check_output(['rpm', '-q', 'cloudify'])
        except (subprocess.CalledProcessError, OSError):
            pass
        else:
            version = rpm_info.split('-')[1]

    return {
        'version': version,
        'edition': get_edition(),
        'distribution': distro,
        'distro_release': distro_release,
    }
