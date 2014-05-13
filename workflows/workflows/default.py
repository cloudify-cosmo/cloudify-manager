

from cloudify.decorators import workflow
from cloudify.workflows.tasks_graph import TaskDependencyGraph


@workflow
def install(ctx, **kwargs):

    graph = TaskDependencyGraph()

    for node in ctx.nodes:

        sequence = graph.sequence()
        sequence.add(
            node.set_state('initializing', return_task=True),
            node.set_state('creating', return_task=True),
            node.send_event('Creating node', return_task=True),
            node.execute_operation('cloudify.interfaces.lifecycle.create',
                                   return_task=True),
            node.set_state('created', return_task=True),
            node.set_state('configuring', return_task=True),
            node.send_event('Configuring node', return_task=True),
            node.execute_operation('cloudify.interfaces.lifecycle.configure',
                                   return_task=True),
            node.set_state('configured', return_task=True),
            node.set_state('starting', return_task=True),
            node.send_event('Starting node', return_task=True),
            node.execute_operation('cloudify.interfaces.lifecycle.start',
                                   return_task=True))
        if _is_host_node(node):
            _host_post_start(node, sequence)
        sequence.add(node.set_state('started', return_task=True))

    graph.execute()


def _is_host_node(node):
    return 'host' in node.type


def _wait_for_host_to_start(host_node, sequence):
        task = host_node.execute_operation(
            'cloudify.interfaces.host.get_state', return_task=True)
        def get_node_state_handler(task):
            return task.async_result.get() is False
        task.on_success = get_node_state_handler
        sequence.add(task)


def _host_post_start(host_node, sequence):
    _wait_for_host_to_start(host_node, sequence)
    if host_node.properties['install_agent'] is True:
        sequence.add(
            host_node.send_event('Installing worker', return_task=True),
            host_node.execute_operation(
                'cloudify.interfaces.worker_installer.install',
                return_task=True),
            host_node.execute_operation(
                'cloudify.interfaces.worker_installer.start',
                return_task=True),
            host_node.send_event('Installing plugin', return_task=True))
        for plugin in host_node.plugins_to_install:
            sequence.add(
                host_node.send_event('Installing plugin: {0}'
                                     .format(plugin['name']),
                                     return_task=True),
                host_node.execute_operation(
                    'cloudify.interfaces.plugin_installer.install',
                    kwargs={'plugin': plugin}, return_task=True))
        sequence.add(host_node.execute_operation(
            'cloudify.interfaces.worker_installer.restart', return_task=True))
