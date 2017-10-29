# ***************************************************************************
# * Copyright (c) 2013 GigaSpaces Technologies Ltd. All rights reserved
# *
# * Licensed under the Apache License, Version 2.0 (the "License");
# * you may not use this file except in compliance with the License.
# * You may obtain a copy of the License at
# *
# *       http://www.apache.org/licenses/LICENSE-2.0
# *
# * Unless required by applicable law or agreed to in writing, software
# * distributed under the License is distributed on an "AS IS" BASIS,
#    * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    * See the License for the specific language governing permissions and
#    * limitations under the License.
# ***************************************************************************/

from setuptools import setup
from setuptools.command.install import install


class InstallCommand(install):

    user_options = install.user_options + [
        ('do-not-fail', None, 'for testing')]
    boolean_options = install.boolean_options + ['do-not-fail']

    def initialize_options(self):
        install.initialize_options(self)
        self.do_not_fail = None

    def finalize_options(self):
        install.finalize_options(self)
        if not self.do_not_fail:
            raise RuntimeError('No one asked me not to fail, so I did')


setup(
    name='mock-rest-plugin',
    version='4.2',
    packages=['mock_rest_plugin'],
    cmdclass={
        'install': InstallCommand,
    }
)
