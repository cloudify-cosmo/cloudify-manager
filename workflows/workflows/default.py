

from cloudify.decorators import workflow
from cloudify.workflows.tasks_graph import TaskDependencyGraph


@workflow
def install(ctx, **kwargs):

    graph = TaskDependencyGraph(ctx)

    for node in ctx.nodes:

        sequence = graph.sequence()
        sequence.add(
            node.set_state('initializing'),
            node.set_state('creating'),
            node.send_event('Creating node'),
            node.execute_operation('cloudify.interfaces.lifecycle.create'),
            node.set_state('created'),
            node.set_state('configuring'),
            node.send_event('Configuring node'),
            node.execute_operation('cloudify.interfaces.lifecycle.configure'),
            node.set_state('configured'),
            node.set_state('starting'),
            node.send_event('Starting node'),
            node.execute_operation('cloudify.interfaces.lifecycle.start'))
        if _is_host_node(node):
            _host_post_start(node, sequence)
        sequence.add(node.set_state('started'))

    graph.execute()


def _is_host_node(node):
    return 'host' in node.type


def _wait_for_host_to_start(host_node, sequence):
        task = host_node.execute_operation(
            'cloudify.interfaces.host.get_state')
        def get_node_state_handler(task):
            return task.async_result.get() is False
        task.on_success = get_node_state_handler
        sequence.add(task)


def _host_post_start(host_node, sequence):
    _wait_for_host_to_start(host_node, sequence)
    if host_node.properties['install_agent'] is True:
        sequence.add(
            host_node.send_event('Installing worker'),
            host_node.execute_operation(
                'cloudify.interfaces.worker_installer.install'),
            host_node.execute_operation(
                'cloudify.interfaces.worker_installer.start'),
            host_node.send_event('Installing plugin'))
        for plugin in host_node.plugins_to_install:
            sequence.add(
                host_node.send_event('Installing plugin: {0}'
                                     .format(plugin['name'])),
                host_node.execute_operation(
                    'cloudify.interfaces.plugin_installer.install',
                    kwargs={'plugin': plugin}))
        sequence.add(host_node.execute_operation(
            'cloudify.interfaces.worker_installer.restart'))
