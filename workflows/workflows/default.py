########
# Copyright (c) 2014 GigaSpaces Technologies Ltd. All rights reserved
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

__author__ = 'dank'


from cloudify.decorators import workflow
from cloudify.workflows.tasks_graph import TaskDependencyGraph, forkjoin


@workflow
def install(ctx, **kwargs):
    """Default install workflow"""

    # instantiate and new graph instance to build install tasks workflow
    graph = TaskDependencyGraph(ctx)

    # We need reference to the create event/state tasks and the start monitor
    # task so we can later create a proper dependency between nodes and
    # their relationships. We use the below tasks as part of a single node
    # workflow, and to create the dependency (at the bottom)
    send_event_creating_tasks = {
        node.id: node.send_event('Creating node')
        for node in ctx.nodes}
    set_state_creating_tasks = {
        node.id: node.set_state('creating')
        for node in ctx.nodes}
    start_monitor_tasks = {
        node.id: node.execute_operation(
            'cloudify.interfaces.monitor_lifecycle.start')
        for node in ctx.nodes}

    # Create node linear task sequences
    # For each node, we create a "task sequence" in which all tasks
    # added to it will be executed in a sequential manner
    for node in ctx.nodes:
        sequence = graph.sequence()

        sequence.add(
            node.set_state('initializing'),
            forkjoin(
                set_state_creating_tasks[node.id],
                send_event_creating_tasks[node.id]
            ),
            node.execute_operation('cloudify.interfaces.lifecycle.create'),
            node.set_state('created'),
            forkjoin(*_relationship_operations(
                node,
                'cloudify.interfaces.relationship_lifecycle.preconfigure')),
            forkjoin(
                node.set_state('configuring'),
                node.send_event('Configuring node')),
            node.execute_operation('cloudify.interfaces.lifecycle.configure'),
            node.set_state('configured'),
            forkjoin(*_relationship_operations(
                node,
                'cloudify.interfaces.relationship_lifecycle.postconfigure')),
            forkjoin(
                node.set_state('starting'),
                node.send_event('Starting node')),
            node.execute_operation('cloudify.interfaces.lifecycle.start'))

        # If this is a host node, we need to add specific host start
        # tasks such as waiting for it to start and installing the agent
        # worker (if necessary)
        if _is_host_node(node):
            sequence.add(*_host_post_start(node))

        sequence.add(
            node.set_state('started'),
            forkjoin(*_relationship_operations(
                node,
                'cloudify.interfaces.relationship_lifecycle.establish')),
            start_monitor_tasks[node.id])

    # Create task dependencies based on node relationships
    # for each node, make a dependency between the create tasks (event, state)
    # and the start monitor task of the target
    for node in ctx.nodes:
        for rel in node.relationships:
            node_set_creating = set_state_creating_tasks[node.id]
            node_event_creating = send_event_creating_tasks[node.id]
            target_monitor_started = start_monitor_tasks[rel.target_id]
            graph.add_dependency(node_set_creating, target_monitor_started)
            graph.add_dependency(node_event_creating, target_monitor_started)

    graph.execute()


@workflow
def uninstall(ctx, **kwargs):
    """Default uninstall workflow"""

    # instantiate a new graph instance to build uninstall tasks workflow
    graph = TaskDependencyGraph(ctx)

    # We need reference to the set deleted state tasks and the stop monitor
    # tasks so we can later create a proper dependency between nodes and
    # their relationships. We use the below tasks as part of a single node
    # workflow, and to create the dependency (at the bottom)
    stop_monitor_tasks = {
        node.id: node.execute_operation(
            'cloudify.interfaces.monitor_lifecycle.stop')
        for node in ctx.nodes}
    set_state_deleted_tasks = {
        node.id: node.set_state('deleted')
        for node in ctx.nodes}

    # We need reference to the stop node tasks and delete node tasks as we
    # augment them with on_failure error handlers later on
    stop_node_tasks = {
        node.id: node.execute_operation(
            'cloudify.interfaces.lifecycle.stop')
        for node in ctx.nodes}
    delete_node_tasks = {
        node.id: node.execute_operation(
            'cloudify.interfaces.lifecycle.delete')
        for node in ctx.nodes}

    # Create node linear task sequences
    # For each node, we create a "task sequence" in which all tasks
    # added to it will be executed in a sequential manner
    for node in ctx.nodes:
        sequence = graph.sequence()

        sequence.add(stop_monitor_tasks[node.id],
                     node.set_state('stopping'),
                     node.send_event('Stopping node'),
                     stop_node_tasks[node.id],
                     node.set_state('stopped'),
                     forkjoin(*_relationship_operations(
                         node,
                         'cloudify.interfaces.relationship_lifecycle'
                         '.unlink')),
                     node.set_state('deleting'),
                     node.send_event('Deleting node'),
                     delete_node_tasks[node.id],
                     set_state_deleted_tasks[node.id])

        # augmenting the stop and delete node tasks with error handlers
        _set_send_node_event_on_error_handler(
            stop_node_tasks[node.id],
            node,
            "Error occurred while stopping node - ignoring...")
        _set_send_node_event_on_error_handler(
            delete_node_tasks[node.id],
            node,
            "Error occurred while deleting node - ignoring...")

    # Create task dependencies based on node relationships
    # for each node, make a dependency between the target's stop monitor task
    # and the deleted state task of the current node
    for node in ctx.nodes:
        for rel in node.relationships:
            target_stop_monitor = stop_monitor_tasks[rel.target_id]
            node_set_deleted = set_state_deleted_tasks[node.id]
            graph.add_dependency(target_stop_monitor, node_set_deleted)

    graph.execute()


def _set_send_node_event_on_error_handler(task, node, error_message):
    def send_node_event_error_handler(tsk):
        node.send_event(error_message)
        return True
    task.on_failure = send_node_event_error_handler


def _relationship_operations(node, operation):
    tasks = []
    for relationship in node.relationships:
        tasks.append(relationship.execute_source_operation(operation))
        tasks.append(relationship.execute_target_operation(operation))
    return tasks


def _is_host_node(node):
    return 'cloudify.types.host' in node.type_hierarchy


def _wait_for_host_to_start(host_node):
    task = host_node.execute_operation(
        'cloudify.interfaces.host.get_state')

    # handler returns True if if get_state returns False,
    # this means, that get_state will be re-executed until
    # get_state returns True
    def node_get_state_handler(tsk):
        return tsk.async_result.get() is False
    task.on_success = node_get_state_handler
    return task


def _host_post_start(host_node):
    tasks = [_wait_for_host_to_start(host_node)]
    if host_node.properties['install_agent'] is True:
        tasks += [
            host_node.send_event('Installing worker'),
            host_node.execute_operation(
                'cloudify.interfaces.worker_installer.install'),
            host_node.execute_operation(
                'cloudify.interfaces.worker_installer.start'),
            host_node.send_event('Installing plugin')]
        for plugin in host_node.plugins_to_install:
            tasks += [
                host_node.send_event('Installing plugin: {0}'
                                     .format(plugin['name'])),
                host_node.execute_operation(
                    'cloudify.interfaces.plugin_installer.install',
                    kwargs={'plugin': plugin})]
        tasks.append(host_node.execute_operation(
            'cloudify.interfaces.worker_installer.restart'))
    return tasks
