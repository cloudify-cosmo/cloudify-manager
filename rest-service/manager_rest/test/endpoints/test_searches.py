from cloudify.models_states import DeploymentState
from cloudify_rest_client.exceptions import CloudifyClientError

from manager_rest.test import base_test
from manager_rest.storage import models
from manager_rest.rest.filters_utils import FilterRule
from manager_rest.rest.search_utils import get_filter_rules


class SearchesTestCase(base_test.BaseServerTestCase):
    LABELS = [{'key1': 'val1'}, {'key1': 'val2'}, {'key2': 'val3'}]
    LABELS_2 = [{'key1': 'val1'}, {'key1': 'val3'}, {'key3': 'val3'}]
    LABELS_3 = [{'key2': 'val4'}, {'key1': 'val3'}]

    FILTER_RULES = [FilterRule('key1', ['val1'], 'any_of', 'label'),
                    FilterRule('key2', [], 'is_not_null', 'label')]

    def test_list_deployments_with_filter_rules(self):
        dep1 = self.put_deployment_with_labels(self.LABELS)
        self.put_deployment_with_labels(self.LABELS_2)
        deployments = self.client.deployments.list(
            filter_rules=self.FILTER_RULES)
        self.assertEqual(len(deployments), 1)
        self.assertEqual(deployments[0].id, dep1.id)
        self.assert_metadata_filtered(deployments, 1)

    def test_list_deployments_with_filter_rules_upper(self):
        self.put_deployment_with_labels(self.LABELS)
        self.put_deployment_with_labels(self.LABELS_2)
        deployments = self.client.deployments.list(
            filter_rules=[FilterRule('KEy1', ['val1'], 'any_of', 'label')])
        self.assertEqual(len(deployments), 2)
        self.assert_metadata_filtered(deployments, 0)
        deployments = self.client.deployments.list(
            filter_rules=[FilterRule('KEy1', ['VaL1'], 'any_of', 'label')])
        self.assertEqual(len(deployments), 0)
        self.assert_metadata_filtered(deployments, 2)

    def test_list_deployments_with_filter_rules_and_filter_id(self):
        self.put_deployment_with_labels(self.LABELS)
        self.put_deployment_with_labels(self.LABELS_2)
        dep3 = self.put_deployment_with_labels(self.LABELS_3)
        self._test_list_resources_with_filter_rules_and_filter_id(
            self.client.deployments_filters, self.client.deployments, dep3)

    def test_list_blueprints_with_filter_rules(self):
        for i in range(1, 3):
            bp_file_name = 'blueprint_with_labels_{0}.yaml'.format(i)
            bp_id = 'blueprint_{0}'.format(i)
            self.put_blueprint(blueprint_id=bp_id,
                               blueprint_file_name=bp_file_name)
        all_blueprints = self.client.blueprints.list(
            filter_rules=[
                FilterRule('bp_key1', ['BP_key1_val1'], 'any_of', 'label')])
        second_blueprint = self.client.blueprints.list(
            filter_rules=[
                FilterRule('bp_key2', ['bp_2_val1'], 'any_of', 'label'),
                FilterRule('bp_key1', [], 'is_not_null', 'label')])
        self.assertEqual(len(all_blueprints), 2)
        self.assert_metadata_filtered(all_blueprints, 0)
        self.assertEqual(len(second_blueprint), 1)
        self.assert_metadata_filtered(second_blueprint, 1)

    def test_list_blueprints_with_filter_rules_and_filter_id(self):
        self.put_blueprint_with_labels(self.LABELS, blueprint_id='bp1')
        self.put_blueprint_with_labels(self.LABELS_2, blueprint_id='bp2')
        bp3 = self.put_blueprint_with_labels(self.LABELS_3,
                                             blueprint_id='bp3')
        self._test_list_resources_with_filter_rules_and_filter_id(
            self.client.blueprints_filters, self.client.blueprints, bp3)

    def test_list_deployments_with_duplicate_filter_rules(self):
        dep1 = self.put_deployment_with_labels(self.LABELS)
        self.put_deployment_with_labels(self.LABELS_2)
        self.create_filter(self.client.deployments_filters, self.FILTER_ID,
                           self.FILTER_RULES)
        deployments = self.client.deployments.list(
            filter_rules=self.FILTER_RULES, filter_id=self.FILTER_ID)
        self.assertEqual(len(deployments), 1)
        self.assertEqual(deployments[0].id, dep1.id)
        self.assert_metadata_filtered(deployments, 1)

    def test_searches_with_search_and_filter_rules(self):
        _, _, _, dep1 = self.put_deployment(deployment_id='dep1',
                                            blueprint_id='bp1')
        self.put_deployment(deployment_id='dep2', blueprint_id='bp2')
        filter_rules_bp1 = [
            FilterRule('blueprint_id', ['bp1'], 'any_of', 'attribute'),
            FilterRule('created_by', ['admin'], 'any_of', 'attribute')
        ]
        deployments = self.client.deployments.list(
            filter_rules=filter_rules_bp1, _search='dep1')
        self.assertEqual(len(deployments), 1)
        self.assertEqual(deployments[0].id, dep1.id)
        deployments = self.client.deployments.list(
            filter_rules=filter_rules_bp1, _search='dep2')
        self.assertEqual(len(deployments), 0)

    def test_searches_get_filter_rules(self):
        self.create_filter(self.client.deployments_filters, self.FILTER_ID,
                           self.FILTER_RULES)
        filter_rules = get_filter_rules(models.Deployment,
                                        models.DeploymentsFilter,
                                        self.FILTER_ID,
                                        self.FILTER_RULES,
                                        None)
        self.assertEqual(filter_rules, self.FILTER_RULES)

    def _test_list_resources_with_filter_rules_and_filter_id(
            self, filters_client, resource_client, compared_resource):
        self.create_filter(filters_client, self.FILTER_ID,
                           [FilterRule('key2', [], 'is_not_null', 'label')])
        resources = resource_client.list(
            filter_rules=[FilterRule('key1', ['val3'], 'any_of', 'label')],
            filter_id=self.FILTER_ID,
            _include=['id']
        )
        self.assertEqual(len(resources), 1)
        self.assertEqual(resources[0].keys(), {'id'})
        self.assertEqual(resources[0]['id'], compared_resource['id'])

    def test_searches_with_search_and_search_name(self):
        self.put_deployment(deployment_id='qwe1', blueprint_id='bp1',
                            display_name='a coil', labels=[{'key': 'a'}])
        self.put_deployment(deployment_id='asd2', blueprint_id='bp2',
                            display_name='a coin', labels=[{'key': 'b'}])
        self.put_deployment(deployment_id='asd3', blueprint_id='bp3',
                            display_name='a toy', labels=[{'key': 'c'}])
        any_blueprint = [
            FilterRule('key', [], 'is_not_null', 'label'),
        ]
        # filter_rules because we want to test a POST to /searches/deployments
        deployments = self.client.deployments.list(
            filter_rules=any_blueprint, _search='asd')
        self.assertEqual(len(deployments), 2)
        deployments = self.client.deployments.list(
            filter_rules=any_blueprint, _search_name='a coi')
        self.assertEqual(len(deployments), 2)
        deployments = self.client.deployments.list(
            filter_rules=any_blueprint, _search='asd', _search_name='coi')
        self.assertEqual(len(deployments), 3)
        self.assertEqual(deployments[0].id, 'qwe1')

    def test_deployments_search_with_constraints(self):
        self.put_deployment(deployment_id='d1', blueprint_id='b1',
                            labels=[{'type': 'test'}, {'one': 'yes'}])
        self.put_deployment(deployment_id='d2', blueprint_id='b2',
                            labels=[{'type': 'test'}])
        self.create_filter(self.client.deployments_filters, 'filter1',
                           [FilterRule('one', ['yes'], 'any_of', 'label')])
        deployments = self.client.deployments.list(
            constraints={'filter_id': 'filter1'})
        self.assertEqual(len(deployments), 1)
        deployments = self.client.deployments.list(
            constraints={'labels': [{'type': 'test'}]})
        self.assertEqual(len(deployments), 2)
        deployments = self.client.deployments.list(
            constraints={'filter_id': 'filter1'}, _search='d2')
        self.assertEqual(len(deployments), 0)

    def test_deployments_search_valid_params(self):
        self.put_deployment(deployment_id='d1', blueprint_id='b1',
                            labels=[{'type': 'test'}, {'one': 'yes'}])
        self.create_filter(self.client.deployments_filters, 'filter1',
                           [FilterRule('one', ['yes'], 'any_of', 'label')])
        self.assertRaisesRegex(
            ValueError, 'not both',
            self.client.deployments.list,
            constraints={'labels': [{'type': 'text'}]},
            filter_id='filter1')
        self.assertRaisesRegex(
            ValueError, 'not both',
            self.client.deployments.list,
            constraints={'labels': [{'type': 'text'}]},
            filter_rules=[FilterRule('one', ['yes'], 'any_of', 'label')])

    def test_deployments_search_installation_status(self):
        bp = models.Blueprint(
            id='bp1',
            creator=self.user,
            tenant=self.tenant,
        )
        for dep_id, state in [
            ('active', DeploymentState.ACTIVE),
            ('inactive', DeploymentState.INACTIVE),
            ('null', None),
        ]:
            models.Deployment(
                id=dep_id,
                blueprint=bp,
                installation_status=state,
                creator=self.user,
                tenant=self.tenant,
            )

        search_all = self.client.deployments.list()
        search_active = self.client.deployments.list(filter_rules=[
            FilterRule(
                'installation_status',
                [DeploymentState.ACTIVE],
                'any_of',
                'attribute'
            ),
        ])
        search_inactive = self.client.deployments.list(filter_rules=[
            FilterRule(
                'installation_status',
                [DeploymentState.INACTIVE],
                'any_of',
                'attribute'
            ),
        ])

        assert len(search_all) == 3
        assert {d.id for d in search_active} == {'active'}
        assert {d.id for d in search_inactive} == {'inactive'}

    def test_secrets_search_by_key(self):
        for key, value in [
            ('secret1', 'value1'),
            ('secret2', 'value2'),
        ]:
            models.Secret(
                id=key,
                value=value,
                creator=self.user,
                tenant=self.tenant,
            )

        search_all = self.client.secrets.list()
        search_secret1 = self.client.secrets.list(_search='secret1')

        assert len(search_all) == 2
        assert [s.key for s in search_secret1] == ['secret1']

    def test_secrets_search_filter_by_key(self):
        for key, value in [
            ('secret1', 'value1'),
            ('secret2', 'value2'),
        ]:
            models.Secret(
                id=key,
                value=value,
                creator=self.user,
                tenant=self.tenant,
            )

        search_secret1 = self.client.secrets.list(filter_rules=[
            FilterRule(
                'key',
                ['secret1'],
                'any_of',
                'attribute'
            )
        ])
        search_secret1_or_secret2 = self.client.secrets.list(filter_rules=[
            FilterRule(
                'key',
                ['secret1', 'secret2'],
                'any_of',
                'attribute'
            )
        ])

        assert [s.key for s in search_secret1] == ['secret1']
        assert {s.key for s in search_secret1_or_secret2} == \
               {'secret1', 'secret2'}

    def test_secrets_filter_by_name_pattern_constraints(self):
        for key, value in [
            ('secret1', 'value1'),
            ('secret2', 'value2'),
            ('secret3', 'value3'),
        ]:
            models.Secret(
                id=key,
                value=value,
                creator=self.user,
                tenant=self.tenant,
            )

        search = self.client.secrets.list(
            constraints={'name_pattern': {'contains': 'ret1'}}
        )
        assert [s.key for s in search] == ['secret1']

        search = self.client.secrets.list(
            constraints={'name_pattern': {'ends_with': 'ret2'}}
        )
        assert [s.key for s in search] == ['secret2']

        search = self.client.secrets.list(
            constraints={'name_pattern': {'starts_with': 'secret'}}
        )
        assert {s.key for s in search} == {'secret1', 'secret2', 'secret3'}

        search = self.client.secrets.list(
            constraints={'name_pattern': {'equals_to': 'secret3'}}
        )
        assert [s.key for s in search] == ['secret3']

        search = self.client.secrets.list(
            constraints={'name_pattern': {'equals_to': 'secret3'}},
            _search='secret1'
        )
        assert [s.key for s in search] == []

    def test_secrets_filter_by_valid_values_constraints(self):
        for key, value in [
            ('secret1', 'value1'),
            ('secret2', 'value2'),
            ('secret3', 'value3'),
        ]:
            models.Secret(
                id=key,
                value=value,
                creator=self.user,
                tenant=self.tenant,
            )

        search = self.client.secrets.list(
            constraints={'valid_values': ['secret1', 'secret2']}
        )
        assert {s.key for s in search} == {'secret1', 'secret2'}

        search = self.client.secrets.list(
            constraints={'valid_values': ['secret1', 'secret2']},
            _search='secret2'
        )
        assert [s.key for s in search] == ['secret2']

        search = self.client.secrets.list(
            constraints={'valid_values': ['secret1', 'secret2']},
            _search='secret3'
        )
        assert [s.key for s in search] == []

    def _create_nodes(self, blueprint_id='bp', deployment_id='dep',
                      node_ids=None):
        node_ids = node_ids or ['node_1', 'node_2']
        bp = models.Blueprint(
            id=blueprint_id,
            creator=self.user,
            tenant=self.tenant,
        )
        dep = models.Deployment(
            id=deployment_id,
            blueprint=bp,
            scaling_groups={},
            creator=self.user,
            tenant=self.tenant,
        )
        nodes = {
            node_id: models.Node(
                id=node_id,
                type='testtype',
                number_of_instances=0,
                deploy_number_of_instances=0,
                max_number_of_instances=0,
                min_number_of_instances=0,
                planned_number_of_instances=0,
                deployment=dep,
                creator=self.user,
                tenant=self.tenant
            )
            for node_id in node_ids
        }
        return nodes

    def test_nodes_search_by_id(self):
        self._create_nodes('b1', 'd1', ['vm', 'http_web_server'])
        self._create_nodes('b2', 'd2', ['vm', 'http_web_server'])

        search_all = self.client.nodes.list()
        search_node_vm = self.client.nodes.list(_search='vm')

        assert len(search_all) == 4
        assert {n.id for n in search_node_vm} == {'vm'}

    def test_nodes_search_filter_by_id(self):
        self._create_nodes('b1', 'd1', ['vm', 'http_web_server'])
        self._create_nodes('b2', 'd2', ['vm', 'http_web_server'])

        search_node_vm = self.client.nodes.list(
            deployment_id='d2',
            filter_rules=[FilterRule('id', ['vm'], 'any_of', 'attribute')]
        )
        search_both_nodes = self.client.nodes.list(
            deployment_id='d1',
            filter_rules=[FilterRule('id', ['vm', 'http_web_server'],
                                     'any_of', 'attribute')]
        )

        assert len([s.id for s in search_node_vm]) == 1
        assert {s.id for s in search_both_nodes} == {'vm', 'http_web_server'}

    def test_nodes_filter_by_name_pattern_constraints(self):
        self._create_nodes('b1', 'd1', ['vm', 'http_web_server'])
        self._create_nodes('b2', 'd2', ['vm', 'http_web_server'])

        search = self.client.nodes.list(
            constraints={
                'deployment_id': 'd1',
                'name_pattern': {'contains': 'web'}
            }
        )
        assert {s.id for s in search} == {'http_web_server'}

        search = self.client.nodes.list(
            constraints={
                'deployment_id': 'd1',
                'name_pattern': {'ends_with': 'server'}
            }
        )
        assert {s.id for s in search} == {'http_web_server'}

        search = self.client.nodes.list(
            constraints={
                'deployment_id': 'd1',
                'name_pattern': {'starts_with': 'http'}
            }
        )
        assert {s.id for s in search} == {'http_web_server'}

        search = self.client.nodes.list(
            constraints={
                'deployment_id': 'd1',
                'name_pattern': {'equals_to': 'vm'}
            }
        )
        assert {s.id for s in search} == {'vm'}

        search = self.client.nodes.list(
            constraints={
                'deployment_id': 'd2',
                'name_pattern': {'equals_to': 'vm'}
            }
        )
        assert {s.id for s in search} == {'vm'}

        search = self.client.nodes.list(
            constraints={
                'deployment_id': 'd1',
                'name_pattern': {'equals_to': 'http_web_server'}
            },
            _search='vm'
        )
        assert [s.id for s in search] == []

        with self.assertRaises(CloudifyClientError):
            self.client.nodes.list(
                constraints={
                    'name_pattern': {'equals_to': 'http_web_server'}
                }
            )

        with self.assertRaises(CloudifyClientError):
            self.client.nodes.list(
                deployment_id='d1',
                constraints={
                    'deployment_id': 'd1',
                }
            )

    def test_nodes_filter_by_valid_values_constraints(self):
        self._create_nodes('b1', 'd1', ['vm', 'http_web_server'])
        self._create_nodes('b2', 'd2', ['vm', 'http_web_server'])

        search = self.client.nodes.list(
            constraints={
                'deployment_id': 'd1',
                'valid_values': ['vm', 'non-existent-node']
            }
        )
        assert {s.id for s in search} == {'vm'}

        search = self.client.nodes.list(
            constraints={
                'deployment_id': 'd1',
                'valid_values': ['foo', 'bar']
            },
            _search='vm'
        )
        assert [s.id for s in search] == []
