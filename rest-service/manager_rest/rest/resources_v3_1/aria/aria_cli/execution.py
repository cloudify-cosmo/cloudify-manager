#########
# Copyright (c) 2017 GigaSpaces Technologies Ltd. All rights reserved
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
from manager_rest.rest import rest_utils
from manager_rest.rest.rest_utils import get_json_and_verify_params

from aria.orchestrator.workflows.core import engine
from aria.orchestrator import execution_preparer
from aria.orchestrator.workflows.executor import process

from ..... import manager_exceptions
from .... import rest_decorators
from . import base


class ARIAExecution(base.BaseARIAEndpoints):

    @rest_decorators.exceptions_handled
    def get(self, execution_id):
        """
        Get Execution by id
        """
        return self.model.execution.get(execution_id).to_dict()

    @rest_decorators.exceptions_handled
    def post(self, execution_id, **kwargs):
        """
        Apply execution action (cancel, force-cancel) by id
        """
        request_dict = get_json_and_verify_params({'action'})
        action = request_dict['action']

        valid_actions = ['cancel', 'force-cancel']

        if action not in valid_actions:
            raise manager_exceptions.BadParametersError(
                'Invalid action: {0}, Valid action values are: {1}'.format(
                    action, valid_actions))

        if action in ('cancel', 'force-cancel'):
            service = self.model.execution.get(execution_id)
            executor = process.ProcessExecutor(self.plugin_manager)

            compiler = execution_preparer.ExecutionPreparer(
                self.model,
                self.resource,
                self.plugin_manager,
                service,
                request_dict['workflow_name']
            )
            workflow_ctx = compiler.prepare(execution_id=execution_id)
            engine_ = engine.Engine(executor)
            engine_.cancel_execution(workflow_ctx)


class ARIAExecutions(base.BaseARIAEndpoints):

    @rest_decorators.create_filters()
    def get(self, _include=None, filters=None, pagination=None, sort=None,
            **kwargs):
        """
        Get an Execution list
        """
        return self._respond_list(
            self.model.execution.list(
                include=_include,
                filters=filters,
                pagination=pagination,
                sort=sort,
                **kwargs
                )
        )

    def post(self, **kwargs):
        """
        Start an execution
        """
        request_dict = rest_utils.get_json_and_verify_params(
            dict(
                service_id={'type': int},
                workflow_name={'type': basestring},
            )
        )

        service = self.model.service.get(request_dict['service_id'])
        executor = process.ProcessExecutor(plugin_manager=self.plugin_manager)

        compiler = execution_preparer.ExecutionPreparer(
            self.model,
            self.resource,
            self.plugin_manager,
            service,
            request_dict['workflow_name']
        )
        workflow_ctx = compiler.prepare(executor=executor)
        engine_ = engine.Engine(executor)
        engine_.execute(workflow_ctx)

        return workflow_ctx.execution.to_dict(
            workflow_ctx.execution.fields() -
            {'created_at', 'started_at', 'ended_at'}), \
            201
