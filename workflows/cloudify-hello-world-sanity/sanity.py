# flake8: noqa

import requests
import copy
import json
import yaml
import sys
import os
import argparse
import path
import sh
from cosmo_manager_rest_client.cosmo_manager_rest_client import CosmoManagerRestClient

#################################
## Arguments setup
#################################

parser = argparse.ArgumentParser()
parser.add_argument('--key_path')
parser.add_argument('--key_name')
parser.add_argument('--host_name')
parser.add_argument('--management_ip')
args = parser.parse_args()

###################################
## Configuration
###################################

key_path = args.key_path
key_name = args.key_name
host_name = args.host_name
management_ip = args.management_ip

image = 67074
region = 'az-2.region-a.geo-1'

hello_world_repo_url = 'https://github.com/CloudifySource/cloudify-hello-world.git'
hello_world_repo_branch = 'develop'

blueprint_repo_dir = path.path('cloudify-hello-world').abspath()
original_blueprint = blueprint_repo_dir / 'openstack' / 'blueprint.yaml'
sanity_blueprint = blueprint_repo_dir / 'openstack' / 'blueprint_sanity.yaml'
original_hello_world = blueprint_repo_dir / 'openstack' / 'hello_world.yaml'
sanity_hello_world = blueprint_repo_dir / 'openstack' / 'hello_world_sanity.yaml'

## Temp dev workaround
cloudify_conf_path = path.path(os.getcwd()) / '.cloudify'
if cloudify_conf_path.exists():
    cloudify_conf_path.remove()

#####################################
## Helper functions and variables
####################################

def out(line): sys.stdout.write(line)
def err(line): sys.stderr.write(line)

cfy = sh.cfy.bake(_out=out, _err=err)
git = sh.git.bake(_out=out, _err=err)

client = CosmoManagerRestClient(management_ip)

def get_manager_state():
    print 'Fetch manager state'
    blueprints = {}
    for blueprint in client.list_blueprints():
        blueprints[blueprint.id] = blueprint
    deployments = {}
    for deployment in client.list_deployments():
        deployments[deployment.id] = deployment
    nodes = {}
    for node in client.list_nodes()['nodes']:
        nodes[node['id']] = node
    workflows = {}
    deployment_nodes = {}
    node_state = {}                                                    
    for deployment_id in deployments.keys():
        workflows[deployment_id] = client.list_workflows(deployment_id)
        deployment_nodes[deployment_id] = client.list_deployment_nodes(
            deployment_id,
            get_reachable_state=True)
        node_state[deployment_id] = {}
        for node in deployment_nodes[deployment_id].nodes:
                node_state[deployment_id][node.id] = client.get_node_state(
                    node.id,
                    get_reachable_state=True,
                    get_runtime_state=True)

    return {
        'blueprints': blueprints,
        'deployments': deployments,
        'workflows': workflows,
        'nodes': nodes,
        'node_state': node_state,
        'deployment_nodes': deployment_nodes
    }

def get_state_delta(before, after):
    after = copy.deepcopy(after)
    for blueprint_id in before['blueprints'].keys():
        del after['blueprints'][blueprint_id]
    for deployment_id in before['deployments'].keys():
        del after['deployments'][deployment_id]
        del after['workflows'][deployment_id]
        del after['deployment_nodes'][deployment_id]
        del after['node_state'][deployment_id]
    for node_id in before['nodes'].keys():
        del after['nodes'][node_id]
    return after

##################################
## Step functions
##################################
def clone_hello_world():
    if not blueprint_repo_dir.isdir():
        git.clone(hello_world_repo_url).wait()
    with blueprint_repo_dir:
        git.checkout(hello_world_repo_branch).wait()

def modify_blueprint():
    # load original yamls    
    blueprint_yaml = yaml.load(original_blueprint.text())
    hello_yaml = yaml.load(original_hello_world.text())

    # make modifications
    blueprint_yaml['imports'][0] = 'hello_world_sanity.yaml'
    hello_yaml['types']['openstack_host']['properties'][1]['worker_config']['key'] = key_path
    hello_yaml['types']['openstack_host']['properties'][2]['nova_config']['region'] = region
    hello_yaml['types']['openstack_host']['properties'][2]['nova_config']['instance']['name'] = host_name
    hello_yaml['types']['openstack_host']['properties'][2]['nova_config']['instance']['image'] = image
    hello_yaml['types']['openstack_host']['properties'][2]['nova_config']['instance']['key_name'] = key_name
    
    # store new yamls
    sanity_blueprint.write_text(yaml.dump(blueprint_yaml))
    sanity_hello_world.write_text(yaml.dump(hello_yaml))

def upload_create_deployment_and_execute():
    before_state = get_manager_state()

    cfy.use(management_ip).wait()
    cfy.blueprints.upload(sanity_blueprint, a='sanity_blueprint').wait()
    cfy.deployments.create('sanity_blueprint', a='sanity_deployment').wait()
    cfy.deployments.execute.install('sanity_deployment').wait()

    after_state = get_manager_state()

    return before_state, after_state


def assert_valid_deployment(before_state, after_state):

    delta = get_state_delta(before_state, after_state)

    assert len(delta['blueprints']) == 1, 'Expected 1 blueprint: {0}'.format(delta)

    blueprint_from_list = delta['blueprints'].values()[0]
    blueprint_by_id = client._blueprints_api.getById(blueprint_from_list.id)
    assert yaml.dump(blueprint_from_list) == yaml.dump(blueprint_by_id)

    assert len(delta['deployments']) == 1, 'Expected 1 deployment: {0}'.format(delta)

    deployment_from_list = delta['deployments'].values()[0]
    deployment_by_id = client._deployments_api.getById(deployment_from_list.id)
    # plan is good enough because it cotains generated ids
    assert deployment_from_list.plan == deployment_by_id.plan

    executions = client._deployments_api.listExecutions(deployment_by_id.id)
    assert len(executions) == 1, 'Expected 1 execution: {0}'.format(executions)

    execution_from_list = executions[0]
    execution_by_id = client._executions_api.getById(execution_from_list.id)
    assert yaml.dump(execution_from_list) == yaml.dump(execution_by_id)

    assert len(delta['deployment_nodes']) == 1, 'Expected 1 deployment_nodes: {0}'.format(delta)
    
    assert len(delta['node_state']) == 1, 'Expected 1 node_state: {0}'.format(delta)
    
    assert len(delta['nodes']) == 2, 'Expected 2 nodes: {0}'.format (delta)
    
    assert len(delta['workflows']) == 1, 'Expected 1 workflows: {0}'.format(delta)

    nodes_state = delta['node_state'].values()[0]
    assert len(nodes_state) == 2, 'Expected 2 node_state: {0}'.format(nodes_state)
    
    public_ip = None
    webserver_node_id = None
    for key, value in nodes_state.items():
        assert 'ip' in value['runtimeInfo'], 'Missing ip in runtimeInfo: {0}'.format(nodes_state)
        if key.startswith('vm'):
            assert 'ips' in value['runtimeInfo'], 'Missing ips in runtimeInfo: {0}'.format(nodes_state)
            private_ip = value['runtimeInfo']['ip']
            ips = value['runtimeInfo']['ips']
            public_ip = filter(lambda ip: ip != private_ip, ips)[0]
            assert value['reachable'] is True, 'vm node should be reachable: {0}'.format(nodes_state)
        else:
            webserver_node_id = key

    events = client.get_execution_events(execution_by_id.id)
    assert len(events) > 0, 'Expected at least 1 event for execution id: {0}'.format(execution_by_id.id)

    web_server_page_response = requests.get('http://{0}:8080'.format(public_ip))
    fail_message = 'Expected to find {0} in web server response: {1}'.format(webserver_node_id, web_server_page_response)
    assert webserver_node_id in web_server_page_response.text, fail_message

##################################
## Steps
##################################

clone_hello_world()
modify_blueprint()
before, after = upload_create_deployment_and_execute()
assert_valid_deployment(before, after)
