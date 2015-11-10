########
# Copyright (c) 2013 GigaSpaces Technologies Ltd. All rights reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
#    * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    * See the License for the specific language governing permissions and
#    * limitations under the License.

from cloudify_agent.app import app

from mock_plugins.cloudify_agent.installer import AgentInstaller


class ConsumerBackedAgentInstaller(AgentInstaller):

    def create(self):
        pass

    def configure(self):
        pass

    def start(self):
        app.control.add_consumer(
            queue=self.agent_queue,
            destination=['celery@cloudify.management']
        )

    def stop(self):
        app.control.cancel_consumer(
            queue=self.agent_queue,
            destination=['celery@cloudify.management']
        )

    def restart(self):
        pass

    def delete(self):
        pass
