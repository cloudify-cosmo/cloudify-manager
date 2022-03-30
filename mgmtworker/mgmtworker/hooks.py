########
# Copyright (c) 2019 Cloudify Platform Ltd. All rights reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
############

import os
import yaml
import logging

from cloudify._compat import parse_version
from cloudify.manager import get_rest_client
from cloudify.constants import EVENTS_EXCHANGE_NAME

from cloudify_agent.worker import (
    CloudifyOperationConsumer,
)

logger = logging.getLogger('mgmtworker')


class HookConsumer(CloudifyOperationConsumer):
    routing_key = 'events.hooks'
    HOOKS_CONFIG_PATH = '/opt/mgmtworker/config/hooks.conf'

    def __init__(self, queue_name, registry, max_workers=5):
        super(HookConsumer, self).__init__(queue_name,
                                           exchange_type='topic',
                                           registry=registry,
                                           threadpool_size=max_workers)
        self.queue = queue_name
        self.exchange = EVENTS_EXCHANGE_NAME

    def handle_task(self, full_task):
        event_type = full_task['event_type']
        hook = self._get_hook(event_type)
        if not hook:
            return
        logger.info(
            'The hook consumer received `{0}` event and the hook '
            'implementation is: `{1}`'.format(event_type,
                                              hook.get('implementation'))
        )

        try:
            task = self._get_task(full_task, hook)
            result = super(HookConsumer, self).handle_task(task)
        except Exception as e:
            result = {'ok': False, 'error': str(e)}
            logger.error('%r, while running the hook triggered by the '
                         'event: %s', e, event_type)
        return result

    def _get_hook(self, event_type):
        if not os.path.exists(self.HOOKS_CONFIG_PATH):
            logger.warn("The hook consumer received `{0}` event but the "
                        "hooks config file doesn't exist".format(event_type))
            return None

        with open(self.HOOKS_CONFIG_PATH) as hooks_conf_file:
            try:
                hooks_yaml = yaml.safe_load(hooks_conf_file)
                hooks_conf = hooks_yaml.get('hooks', {}) if hooks_yaml else {}
            except yaml.YAMLError:
                logger.error(
                    "The hook consumer received `{0}` event but the hook "
                    "config file is invalid yaml".format(event_type)
                )
                return None

        for hook in hooks_conf:
            if hook.get('event_type') == event_type:
                return hook
        logger.info("The hook consumer received `{0}` event but didn't find a "
                    "compatible hook in the configuration".format(event_type))
        return None

    def _get_task(self, full_task, hook):
        hook_context, operation_context = self._get_contexts(
            full_task,
            hook['implementation']
        )
        task = {
            'cloudify_task': {
                'kwargs': {
                    '__cloudify_context': operation_context
                },
                'args': [hook_context]
            }
        }
        kwargs = hook.get('inputs') or {}
        task['cloudify_task']['kwargs'].update(kwargs)
        return task

    def _get_contexts(self, full_task, implementation):
        hook_context = full_task['context']
        tenant = hook_context.pop('tenant')
        tenant_name = tenant.get('name')
        hook_context['tenant_name'] = tenant.get('name')
        hook_context['event_type'] = full_task['event_type']
        hook_context['timestamp'] = full_task['timestamp']
        hook_context['arguments'] = full_task['message']['arguments']
        token = hook_context['rest_token']
        operation_context = dict(
            type='hook',
            tenant=tenant,
            no_ctx_kwarg=True,
            task_target=self.queue,
            tenant_name=tenant_name,
            rest_token=token,
            plugin=self._get_plugin(tenant_name, implementation, token),
            execution_id=hook_context['execution_id']
        )

        if operation_context['plugin']:
            split_task_name = implementation.split('.')[1:]
            operation_context['task_name'] = '.'.join(split_task_name)
        else:
            operation_context['task_name'] = implementation
        return hook_context, operation_context

    def _get_plugin(self, tenant_name, implementation, token):
        package_name = implementation.split('.')[0]
        filter_plugin = {'package_name': package_name}
        rest_client = get_rest_client(tenant=tenant_name, api_token=token)
        plugins = rest_client.plugins.list(**filter_plugin)
        if not plugins:
            return {}

        plugins.sort(key=lambda p: parse_version(p.package_version),
                     reverse=True)
        return {
            'name': package_name,
            'package_name': package_name,
            'package_version': plugins[0]['package_version'],
            'visibility': plugins[0]['visibility']
        }
