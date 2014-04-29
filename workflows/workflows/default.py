import time

from cloudify.decorators import workflow


@workflow
def install(ctx, **kwargs):
    for node in ctx.nodes:
        node.set_state('initializing')
        node.set_state('creating')
        node.execute_operation('cloudify.interfaces.lifecycle.create')
        node.set_state('created')
        node.set_state('configuring')
        node.execute_operation('cloudify.interfaces.lifecycle.configure')
        node.set_state('configured')
        node.set_state('starting')
        node.execute_operation('cloudify.interfaces.lifecycle.start')
        if _is_host_node(node):
            _host_post_start(ctx, node)
        node.set_state('started')


def _is_host_node(node):
    return 'host' in node.type


def _wait_for_host_to_start(host_node):
    while True:
        state = host_node.execute('cloudify.interfaces.host.get_state')
        if state is True:
            break
        time.sleep(5)


def _host_post_start(ctx, host_node):
    _wait_for_host_to_start(host_node)
    if host_node.properties['install_agent'] is True:
        ctx.send_event('Installing worker')
        host_node.execute_operation(
            'cloudify.interfaces.worker_installer.install')
        host_node.execute_operation(
            'cloudify.interfaces.worker_installer.start')
        ctx.send_event('Installing plugin')
        for plugin in host_node.plugins_to_install:
            ctx.send_event('Installing plugin: {0}'.format(plugin['name']))
            host_node.execute_operation(
                'cloudify.interfaces.plugin_installer.install', plugin=plugin)
        host_node.execute_operation(
            'cloudify.interfaces.worker_installer.restart')
