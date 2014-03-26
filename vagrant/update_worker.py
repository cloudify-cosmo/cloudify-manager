# /****************************************************************************
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
# *****************************************************************************

__author__ = 'elip'


def update_worker():

    """
    Use this method to connect to an existing management machine and
    update the worker with new plugins from
    github.
    Be sure to push your changes before running this.
    """
    from test import get_remote_runner
    runner = get_remote_runner()
    runner.run("python2.7 /vagrant/bootstrap_lxc_manager.py "
               "--update_only=True")


update_worker()
