#########
# Copyright (c) 2013 GigaSpaces Technologies Ltd. All rights reserved
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

__author__ = 'dan'


from base_test import BaseServerTestCase
from test_blueprints import post_blueprint_args


class DeploymentsTestCase(BaseServerTestCase):

    DEPLOYMENT_ID = 'deployment'

    def _put_test_deployment(self):
        blueprint_response = self.post_file(*post_blueprint_args()).json
        blueprint_id = blueprint_response['id']
        #Execute post deployment
        deployment_response = self.put(
            '/deployments/{0}'.format(self.DEPLOYMENT_ID),
            {'blueprintId': blueprint_id}).json
        return (blueprint_id, deployment_response['id'], blueprint_response,
                deployment_response)

    def test_get_empty(self):
        result = self.get('/deployments')
        self.assertEquals(0, len(result.json))

    def test_put(self):
        (blueprint_id,
         deployment_id,
         blueprint_response,
         deployment_response) = self._put_test_deployment()

        self.assertEquals(deployment_id, self.DEPLOYMENT_ID)
        self.assertEquals(blueprint_id, deployment_response['blueprintId'])
        self.assertIsNotNone(deployment_response['createdAt'])
        self.assertIsNotNone(deployment_response['updatedAt'])
        typed_blueprint_plan = blueprint_response['plan']
        typed_deployment_plan = deployment_response['plan']
        self.assertEquals(typed_blueprint_plan['name'],
                          typed_deployment_plan['name'])

    def test_deployment_already_exists(self):
        (blueprint_id,
         deployment_id,
         blueprint_response,
         deployment_response) = self._put_test_deployment()
        deployment_response = self.put(
            '/deployments/{0}'.format(self.DEPLOYMENT_ID),
            {'blueprintId': blueprint_id})
        self.assertTrue('already exists' in
                        deployment_response.json['message'])
        self.assertEqual(409, deployment_response.status_code)

    def test_get_by_id(self):
        (blueprint_id, deployment_id, blueprint_response,
         deployment_response) = self._put_test_deployment()

        single_deployment = self.get('/deployments/{0}'
                                     .format(deployment_id)).json
        self.assertEquals(deployment_id, single_deployment['id'])
        self.assertEquals(deployment_response['blueprintId'],
                          single_deployment['blueprintId'])
        self.assertEquals(deployment_response['id'],
                          single_deployment['id'])
        self.assertEquals(deployment_response['createdAt'],
                          single_deployment['createdAt'])
        self.assertEquals(deployment_response['createdAt'],
                          single_deployment['updatedAt'])
        self.assertEquals(deployment_response['plan'],
                          single_deployment['plan'])

    def test_get(self):
        (blueprint_id, deployment_id, blueprint_response,
         deployment_response) = self._put_test_deployment()

        get_deployments_response = self.get('/deployments').json
        self.assertEquals(1, len(get_deployments_response))
        single_deployment = get_deployments_response[0]
        self.assertEquals(deployment_id, single_deployment['id'])
        self.assertEquals(deployment_response['blueprintId'],
                          single_deployment['blueprintId'])
        self.assertEquals(deployment_response['id'],
                          single_deployment['id'])
        self.assertEquals(deployment_response['createdAt'],
                          single_deployment['createdAt'])
        self.assertEquals(deployment_response['createdAt'],
                          single_deployment['updatedAt'])
        self.assertEquals(deployment_response['plan'],
                          single_deployment['plan'])

    def test_get_blueprints_id_executions_empty(self):
        (blueprint_id, deployment_id, blueprint_response,
         deployment_response) = self._put_test_deployment()
        get_executions = self.get('/deployments/{0}/executions'
                                  .format(deployment_response['id'])).json
        self.assertEquals(len(get_executions), 0)

    def test_get_execution_by_id(self):
        (blueprint_id, deployment_id, blueprint_response,
         deployment_response) = self._put_test_deployment()

        resource_path = '/deployments/{0}/executions'.format(deployment_id)
        execution = self.post(resource_path, {
            'workflowId': 'install'
        }).json
        get_execution_resource = '/executions/{0}'.format(execution['id'])
        get_execution = self.get(get_execution_resource).json
        self.assertEquals(get_execution['status'], 'terminated')
        self.assertEquals(get_execution['blueprintId'], blueprint_id)
        self.assertEquals(get_execution['deploymentId'],
                          deployment_response['id'])
        self.assertIsNotNone(get_execution['createdAt'])

        return execution

    def test_cancel_execution_by_id(self):
        execution = self.test_get_execution_by_id()
        resource_path = '/executions/{0}'.format(execution['id'])
        cancel_response = self.post(resource_path, {
            'action': 'cancel'
        }).json
        self.assertEquals(execution, cancel_response)

    def test_cancel_non_existent_execution(self):
        resource_path = '/executions/do_not_exist'
        cancel_response = self.post(resource_path, {
            'action': 'cancel'
        })
        self.assertEquals(cancel_response.status_code, 404)

    def test_cancel_bad_action(self):
        execution = self.test_get_execution_by_id()
        resource_path = '/executions/{0}'.format(execution['id'])
        cancel_response = self.post(resource_path, {
            'action': 'not_really_cancel'
        })
        self.assertEquals(cancel_response.status_code, 400)

    def test_cancel_no_action(self):
        execution = self.test_get_execution_by_id()
        resource_path = '/executions/{0}'.format(execution['id'])
        cancel_response = self.post(resource_path, {
            'not_action': 'some_value'
        })
        self.assertEquals(cancel_response.status_code, 400)

    def test_get_executions_of_deployment(self):
        (blueprint_id, deployment_id, blueprint_response,
         deployment_response) = self._put_test_deployment()

        resource_path = '/deployments/{0}/executions'.format(deployment_id)
        execution = self.post(resource_path, {
            'workflowId': 'install'
        }).json
        self.assertEquals(execution['workflowId'], 'install')
        self.assertEquals(execution['blueprintId'], blueprint_id)
        self.assertEquals(execution['deploymentId'], deployment_response['id'])
        self.assertIsNotNone(execution['createdAt'])
        get_execution = self.get(resource_path).json
        self.assertEquals(1, len(get_execution))
        self.assertEquals(execution, get_execution[0])

    def test_get_workflows_of_deployment(self):
        (blueprint_id, deployment_id, blueprint_response,
         deployment_response) = self._put_test_deployment()

        resource_path = '/deployments/{0}/workflows'.format(deployment_id)
        workflows = self.get(resource_path).json
        self.assertEquals(workflows['blueprintId'], blueprint_id)
        self.assertEquals(workflows['deploymentId'], deployment_id)
        self.assertEquals(2, len(workflows['workflows']))
        self.assertEquals(workflows['workflows'][0]['name'], 'install')
        self.assertTrue('createdAt' in workflows['workflows'][0])
        self.assertEquals(workflows['workflows'][1]['name'], 'uninstall')
        self.assertTrue('createdAt' in workflows['workflows'][1])

    def test_get_nodes_of_deployment(self):

        (blueprint_id, deployment_id, blueprint_response,
         deployment_response) = self._put_test_deployment()

        resource_path = '/deployments/{0}/nodes'\
                        .format(deployment_id)
        nodes = self.get(resource_path,
                         query_params={'reachable': 'False'}).json
        self.assertEquals(deployment_id, nodes['deploymentId'])
        self.assertEquals(2, len(nodes['nodes']))

        def assert_node_exists(starts_with):
            self.assertTrue(any(map(
                lambda n: n['id'].startswith(starts_with),
                nodes['nodes'])),
                'Failed finding node with prefix {0}'.format(starts_with))
        assert_node_exists('vm')
        assert_node_exists('http_web_server')

    # rename and run manually after starting a riemann server
    def _test_get_nodes_of_deployment_with_reachable(self):

        import bernhard
        import json
        client = bernhard.Client()

        def send(n_id, reachable):
            tags = ['name={0}'.format(n_id)]
            if reachable:
                tags.append('reachable')
            client.send({
                'host': 'host',
                'service': n_id,
                'tags': tags
            })

        (blueprint_id, deployment_id, blueprint_response,
         deployment_response) = self._put_test_deployment()

        for node in json.loads(deployment_response['plan'])['nodes']:
            node_id = node['id']
            if 'mezzanine_db' in node_id:
                send(node_id, False)
            elif 'postgres_host' in node_id:
                send(node_id, False)
                send(node_id, True)
            elif 'postgres_server' in node_id:
                send(node_id, True)
            if 'mezzanine_app' in node_id:
                send(node_id, False)
            elif 'nginx' in node_id:
                send(node_id, False)
                send(node_id, True)
            elif 'unicorn' in node_id:
                send(node_id, True)
            elif 'webserver_host' in node_id:
                send(node_id, False)

        resource_path = '/deployments/{0}/nodes?reachable=true'\
                        .format(deployment_id)
        nodes = self.get(resource_path).json
        self.assertEquals(deployment_id, nodes['deploymentId'])
        self.assertEquals(7, len(nodes['nodes']))

        def assert_node_value(starts_with, reachable):
            self.assertTrue(any(map(
                lambda n: n['id'].startswith(starts_with) and
                n['reachable'] == reachable,
                nodes['nodes'])),
                'Failed finding node with prefix {0}'
                .format(starts_with))
        assert_node_value('mezzanine_db', False)
        assert_node_value('postgres_host', True)
        assert_node_value('postgres_server', True)
        assert_node_value('mezzanine_app', False)
        assert_node_value('nginx', True)
        assert_node_value('unicorn', True)
        assert_node_value('webserver_host', False)
