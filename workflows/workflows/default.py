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

    # We need reference to the create event/state tasks and the started
    # task so we can later create a proper dependency between nodes and
    # their relationships. We use the below tasks as part of a single node
    # workflow, and to create the dependency (at the bottom)
    send_event_creating_tasks = {}
    set_state_creating_tasks = {}
    set_state_started_tasks = {}
    for node in ctx.nodes:
        for instance in node.instances:
            send_event_creating_tasks[instance.id] = instance.send_event(
                'Creating node')
            set_state_creating_tasks[instance.id] = instance.set_state(
                'creating')
            set_state_started_tasks[instance.id] = instance.set_state(
                'started')

    # Create node linear task sequences
    # For each node, we create a "task sequence" in which all tasks
    # added to it will be executed in a sequential manner
    for node in ctx.nodes:
        for instance in node.instances:
            sequence = graph.sequence()

            sequence.add(
                instance.set_state('initializing'),
                forkjoin(
                    set_state_creating_tasks[instance.id],
                    send_event_creating_tasks[instance.id]
                ),
                instance.execute_operation(
                    'cloudify.interfaces.lifecycle.create'),
                instance.set_state('created'),
                forkjoin(*_relationship_operations(
                    instance,
                    'cloudify.interfaces.relationship_lifecycle.preconfigure'
                )),
                forkjoin(
                    instance.set_state('configuring'),
                    instance.send_event('Configuring node')),
                instance.execute_operation(
                    'cloudify.interfaces.lifecycle.configure'),
                instance.set_state('configured'),
                forkjoin(*_relationship_operations(
                    instance,
                    'cloudify.interfaces.relationship_lifecycle.postconfigure'
                )),
                forkjoin(
                    instance.set_state('starting'),
                    instance.send_event('Starting node')),
                instance.execute_operation(
                    'cloudify.interfaces.lifecycle.start'))

            # If this is a host node, we need to add specific host start
            # tasks such as waiting for it to start and installing the agent
            # worker (if necessary)
            if _is_host_node(instance):
                sequence.add(*_host_post_start(instance))

            sequence.add(
                set_state_started_tasks[instance.id],
                forkjoin(
                    instance.execute_operation(
                        'cloudify.interfaces.monitor_lifecycle.start'),
                    *_relationship_operations(
                        instance,
                        'cloudify.interfaces.relationship_lifecycle.establish'
                    )))

    # Create task dependencies based on node relationships
    # for each node, make a dependency between the create tasks (event, state)
    # and the started state task of the target
    for node in ctx.nodes:
        for instance in node.instances:
            for rel in instance.relationships:
                node_set_creating = set_state_creating_tasks[instance.id]
                node_event_creating = send_event_creating_tasks[instance.id]
                target_set_started = set_state_started_tasks[rel.target_id]
                graph.add_dependency(node_set_creating, target_set_started)
                graph.add_dependency(node_event_creating, target_set_started)

    graph.execute()


@workflow
def uninstall(ctx, **kwargs):
    """Default uninstall workflow"""

    # instantiate a new graph instance to build uninstall tasks workflow
    graph = TaskDependencyGraph(ctx)

    set_state_stopping_tasks = {}
    set_state_deleted_tasks = {}
    stop_node_tasks = {}
    stop_monitor_tasks = {}
    delete_node_tasks = {}
    for node in ctx.nodes:
        for instance in node.instances:
            # We need reference to the set deleted state tasks and the set
            # stopping state tasks so we can later create a proper dependency
            # between nodes and their relationships. We use the below tasks as
            # part of a single node workflow, and to create the dependency
            # (at the bottom)
            set_state_stopping_tasks[instance.id] = instance.set_state(
                'stopping')
            set_state_deleted_tasks[instance.id] = instance.set_state(
                'deleted')

            # We need reference to the stop node tasks, stop monitor tasks and
            # delete node tasks as we augment them with on_failure error
            # handlers # later on
            stop_node_tasks[instance.id] = instance.execute_operation(
                'cloudify.interfaces.lifecycle.stop')
            stop_monitor_tasks[instance.id] = instance.execute_operation(
                'cloudify.interfaces.monitor_lifecycle.stop')
            delete_node_tasks[instance.id] = instance.execute_operation(
                'cloudify.interfaces.lifecycle.delete')

    # Create node linear task sequences
    # For each node, we create a "task sequence" in which all tasks
    # added to it will be executed in a sequential manner
    for node in ctx.nodes:
        for instance in node.instances:
            sequence = graph.sequence()

            sequence.add(set_state_stopping_tasks[instance.id],
                         instance.send_event('Stopping node'),
                         stop_node_tasks[instance.id],
                         instance.set_state('stopped'),
                         forkjoin(*_relationship_operations(
                             instance,
                             'cloudify.interfaces.relationship_lifecycle'
                             '.unlink')),
                         instance.set_state('deleting'),
                         instance.send_event('Deleting node'),
                         delete_node_tasks[instance.id],
                         set_state_deleted_tasks[instance.id])

            # adding the stop monitor task not as a part of the sequence,
            # as it can happen in parallel with any other task, and is only
            # dependent on the set node state 'stopping' task
            graph.add_task(stop_monitor_tasks[instance.id])
            graph.add_dependency(stop_monitor_tasks[instance.id],
                                 set_state_stopping_tasks[instance.id])

            # augmenting the stop node, stop monitor and delete node tasks with
            # error handlers
            _set_send_node_event_on_error_handler(
                stop_node_tasks[instance.id],
                instance,
                "Error occurred while stopping node - ignoring...")
            _set_send_node_event_on_error_handler(
                stop_monitor_tasks[instance.id],
                instance,
                "Error occurred while stopping monitor - ignoring...")
            _set_send_node_event_on_error_handler(
                delete_node_tasks[instance.id],
                instance,
                "Error occurred while deleting node - ignoring...")

    # Create task dependencies based on node relationships
    # for each node, make a dependency between the target's stopping task
    # and the deleted state task of the current node
    for node in ctx.nodes:
        for instance in node.instances:
            for rel in instance.relationships:
                target_set_stopping = set_state_stopping_tasks[rel.target_id]
                node_set_deleted = set_state_deleted_tasks[instance.id]
                graph.add_dependency(target_set_stopping, node_set_deleted)

    graph.execute()


def _set_send_node_event_on_error_handler(task, node_instance, error_message):
    def send_node_event_error_handler(tsk):
        node_instance.send_event(error_message)
        return True
    task.on_failure = send_node_event_error_handler


def _relationship_operations(node_instance, operation):
    tasks = []
    for relationship in node_instance.relationships:
        tasks.append(relationship.execute_source_operation(operation))
        tasks.append(relationship.execute_target_operation(operation))
    return tasks


def _is_host_node(node_instance):
    return 'cloudify.types.host' in node_instance.node.type_hierarchy


def _wait_for_host_to_start(host_node_instance):
    task = host_node_instance.execute_operation(
        'cloudify.interfaces.host.get_state')

    # handler returns True if if get_state returns False,
    # this means, that get_state will be re-executed until
    # get_state returns True
    def node_get_state_handler(tsk):
        return tsk.async_result.get() is False
    task.on_success = node_get_state_handler
    return task


def _host_post_start(host_node_instance):
    tasks = [_wait_for_host_to_start(host_node_instance)]
    if host_node_instance.node.properties['install_agent'] is True:
        tasks += [
            host_node_instance.send_event('Installing worker'),
            host_node_instance.execute_operation(
                'cloudify.interfaces.worker_installer.install'),
            host_node_instance.execute_operation(
                'cloudify.interfaces.worker_installer.start'),
            host_node_instance.send_event('Installing plugin')]

        tasks += [
            host_node_instance.send_event('Installing plugins: {0}'.format(
                host_node_instance.plugins_to_install)),
            host_node_instance.execute_operation(
                'cloudify.interfaces.plugin_installer.install',
                kwargs={'plugins': host_node_instance.plugins_to_install})]

        tasks.append(host_node_instance.execute_operation(
            'cloudify.interfaces.worker_installer.restart'))
    return tasks
