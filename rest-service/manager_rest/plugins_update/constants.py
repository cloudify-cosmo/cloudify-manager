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

from collections import namedtuple

PluginsUpdatePhases = namedtuple('PluginUpdatePhases', ['INITIAL', 'FINAL'])
PHASES = PluginsUpdatePhases(INITIAL='initiate', FINAL='finalize')

PluginsUpdateStates = namedtuple('PluginsUpdateStates',
                                 ['UPDATING',
                                  'EXECUTING_WORKFLOW',
                                  'FINALIZING',
                                  'SUCCESSFUL',
                                  'FAILED',
                                  'NO_CHANGES_REQUIRED'])
STATES = PluginsUpdateStates(UPDATING='updating',
                             EXECUTING_WORKFLOW='executing_workflow',
                             FINALIZING='finalizing',
                             SUCCESSFUL='successful',
                             FAILED='failed',
                             NO_CHANGES_REQUIRED='no_changes_required')
NOT_ACTIVE_STATES = (STATES.SUCCESSFUL,
                     STATES.FAILED,
                     STATES.NO_CHANGES_REQUIRED)
ACTIVE_STATES = [state for state in STATES if state not in NOT_ACTIVE_STATES]

PLUGIN_UPDATE_WORKFLOW = 'cloudify_system_workflows.plugins.update'
