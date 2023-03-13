from dataclasses import dataclass
import json
import os
import shutil
from tempfile import mkdtemp
from unittest import mock

import pytest

from cloudify_rest_client.responses import ListResponse

from cloudify_system_workflows.snapshots.snapshot_restore import (
    EMPTY_B64_ZIP,
    SnapshotRestore,
)


PARTIAL_TENANTS = {'anothertenant'}
TENANTS = {'default_tenant', 'shared', 'other'}
IDD_DEPENDENCY_CREATOR =\
    'nodes.n1.operations.cloudify.interfaces.lifecycle.create.inputs.'\
    'lifecycle_operation.get_capability'
PARTIAL_SNAP_EXPECTED_CALLS = {
    'tenants': {
        'create': {
            'expected': {
                None: [
                    mock.call(rabbitmq_password='apassword',
                              tenant_name='arbitrary'),
                ],
            },
            'sort_key': 'tenant_name',
        },
    },
    'executions': {
        'create': {
            'expected': {
                'anothertenant': [
                    mock.call(
                        created_at='2022-11-25T15:13:17.930Z',
                        ended_at='2022-11-25T15:13:19.979Z',
                        error='',
                        parameters={},
                        workflow_id='upload_blueprint',
                        started_at='2022-11-25T15:13:18.858Z',
                        allow_custom_parameters=True,
                        deployment_id='',
                        created_by='admin',
                        execution_id='anexecid',
                        force_status='terminated',
                        dry_run=False,
                    ),
                ],
            },
            'sort_key': 'execution_id',
        },
    },
    'tasks_graphs': {
        'create': {
            'expected': {
                'anothertenant': [
                    mock.call(
                        created_at='2022-11-25T15:14:39.191Z',
                        name='update_check_drift',
                        execution_id='anexecid',
                        operations=[
                            {
                                'created_at': '2022-11-25T15:14:39.191Z',
                                'id': '184e9c1a-b951-4954-a566-60dc5822453a',
                                'name': 'NOP',
                                'state': 'pending',
                                'dependencies': [],
                                'type': 'NOPLocalWorkflowTask',
                                'parameters': {},
                                'manager_name': None,
                                'agent_name': None
                            },
                        ],
                        graph_id='6d4e2e5e-87aa-471b-a1e0-4bc8a48a4ec3'
                    ),
                    mock.call(
                        created_at='2022-11-25T15:14:19.203Z',
                        name='install',
                        execution_id='otherexec',
                        operations=[],
                        graph_id='595734d3-1535-4894-b366-ae36e52ca27c'
                    )
                ],
            },
            'sort_key': '',
        },
    },
}
EXPECTED_CALLS = {
    'tenants': {
        'create': {
            'expected': {
                None: [
                    # We don't expect to try to recreate default_client,
                    # because it should already exist
                    mock.call(rabbitmq_password='ilikecake',
                              tenant_name='other'),
                    mock.call(rabbitmq_password='andbiscuits',
                              tenant_name='shared'),
                ],
            },
            'sort_key': 'tenant_name',
        },
        'add_user_group': {
            'expected': {
                None: [
                    mock.call('other', tenant_name='other', role='manager'),
                ],
            },
            'sort_key': 'tenant_name',
        },
        'add_user': {
            'expected': {
                None: [
                    mock.call('ontenant', tenant_name='shared',
                              role='viewer'),
                ],
            },
            'sort_key': 'tenant_name',
        },
    },
    'permissions': {
        'list': {
            'expected': {None: [mock.call()]},
            'sort_key': '',
        },
        'add': {
            'expected': {
                None: [
                    # We don't expect the getting started permission because
                    # we return it in our mock permission listing, and don't
                    # want to recreate perms.
                    mock.call(role='sys_admin', permission='all_tenants'),
                    mock.call(role='sys_admin', permission='administrators'),
                    mock.call(role='manager', permission='administrators'),
                    mock.call(role='sys_admin',
                              permission='create_global_resource'),
                ],
            },
            'sort_key': 'permission',
        },
    },
    'user_groups': {
        'create': {
            'expected': {
                None: [
                    mock.call(role='default', group_name='other',
                              ldap_group_dn=None)
                ],
            },
            'sort_key': 'group_name',
        },
        'add_user': {
            'expected': {
                None: [
                    mock.call('other', 'other')
                ],
            },
            'sort_key': '',
        },
    },
    'users': {
        'create': {
            'expected': {
                None: [
                    # admin user should be skipped as it will already exist
                    mock.call(username='other', role='default',
                              created_at='2022-11-25T15:12:50.148Z',
                              first_login_at='2022-11-25T15:14:44.888Z',
                              last_login_at='2022-11-25T15:16:15.094Z',
                              password='$pbkdf2-def456', is_prehashed=True),
                    mock.call(username='ontenant', role='default',
                              created_at='2022-11-25T15:12:50.819Z',
                              first_login_at=None, last_login_at=None,
                              password='$pbkdf2-ghi789', is_prehashed=True),
                ],
            },
            'sort_key': 'username',
        },
    },
    'sites': {
        'create': {
            'expected': {
                'default_tenant': [
                    mock.call(created_at='2022-11-25T15:13:15.597Z',
                              visibility='tenant', name='defaultsite',
                              created_by='admin', location=None),
                ],
                'other': [
                    mock.call(created_at='2022-11-25T15:14:45.848Z',
                              visibility='tenant', name='othersite',
                              created_by='other', location=None),
                ],
                'shared': [
                    mock.call(created_at='2022-11-25T15:13:04.942Z',
                              visibility='global', name='sharedsite',
                              created_by='admin', location=None),
                ],
            },
            'sort_key': 'name',
        },
    },
    'secrets': {
        'import_secrets': {
            'expected': {
                'default_tenant': [
                    mock.call(
                        secrets_list=[
                            {'key': 'fakedata', 'value': 'something',
                             'visibility': 'tenant',
                             'tenant_name': 'default_tenant',
                             'is_hidden_value': False,
                             'encrypted': False, 'creator': 'admin',
                             'created_at': '2022-11-25T15:13:16.267Z'},
                        ],
                    ),
                ],
                'shared': [
                    mock.call(
                        secrets_list=[
                            {'key': 'agent_key', 'value': 'somekey',
                             'visibility': 'global', 'tenant_name': 'shared',
                             'is_hidden_value': False, 'encrypted': False,
                             'creator': 'admin',
                             'created_at': '2022-11-25T15:13:13.954Z'},
                        ],
                    ),
                ],
            },
            'sort_key': '',
        },
    },
    'plugins': {
        'upload': {
            'expected': {
                'default_tenant': [
                    mock.call(
                        visibility='tenant',
                        plugin_path=(
                            '{tempdir}/tenants/default_tenant/'
                            'plugins_archives/'
                            '3ea7f689-5eb3-46b6-a0ea-1c981e0ecb1c.zip'
                        ),
                        _plugin_id='3ea7f689-5eb3-46b6-a0ea-1c981e0ecb1c',
                        _uploaded_at='2022-11-25T15:13:17.032Z',
                        plugin_title='fakecloud-plugin',
                        _created_by='admin'
                    ),
                    mock.call(
                        visibility='tenant',
                        plugin_path=(
                            '{tempdir}/tenants/default_tenant/'
                            'plugins_archives/'
                            'da6daad8-76dd-4e32-afc1-aac75c622bb3.zip'
                        ),
                        _plugin_id='da6daad8-76dd-4e32-afc1-aac75c622bb3',
                        _uploaded_at='2022-11-25T15:14:28.026Z',
                        plugin_title='fakecloud-plugin',
                        _created_by='admin',
                    ),
                ],
                'shared': [
                    mock.call(
                        visibility='global',
                        plugin_path=(
                            '{tempdir}/tenants/shared/plugins_archives/'
                            '2a90a853-2882-49ea-a0a8-d482ed8cf9d5.zip'
                        ),
                        _plugin_id='2a90a853-2882-49ea-a0a8-d482ed8cf9d5',
                        _uploaded_at='2022-11-25T15:13:05.842Z',
                        plugin_title='test-plugin',
                        _created_by='admin',
                    ),
                ],
            },
            'sort_key': '_plugin_id',
        },
    },
    'blueprints_filters': {
        'create': {
            'expected': {
                'default_tenant': [
                    mock.call(
                        created_at='2022-11-25T15:14:24.522Z',
                        visibility='tenant', created_by='admin',
                        filter_id='fakecloudfilter',
                        filter_rules=[
                            {'key': 'cloudtype',
                             'values': ['fakecloud'],
                             'operator': 'any_of', 'type': 'label'},
                        ],
                    ),
                ],
            },
            'sort_key': 'filter_id',
        },
    },
    'deployments_filters': {
        'create': {
            'expected': {
                'default_tenant': [
                    mock.call(
                        created_at='2022-11-25T15:14:25.810Z',
                        visibility='tenant',
                        created_by='admin',
                        filter_id='fakecloudfilter',
                        filter_rules=[
                            {
                                'key': 'cake',
                                'values': ['untrue'],
                                'operator': 'any_of',
                                'type': 'label'
                            }
                        ]
                    )
                ],
            },
            'sort_key': 'filter_id',
        },
    },
    'blueprints': {
        'publish_archive': {
            'expected': {
                'default_tenant': [
                    mock.call(
                        created_at='2022-11-25T15:13:17.907Z',
                        visibility='tenant',
                        created_by='admin',
                        archive_location=(
                            '{tempdir}/tenants/default_tenant/'
                            'blueprints_archives/fakecloud.zip'
                        ),
                        skip_execution=True,
                        blueprint_id='fakecloud',
                        blueprint_filename='bpfakecloud.yaml',
                        async_upload=True,
                    ),
                    mock.call(
                        created_at='2022-11-25T15:13:21.556Z',
                        visibility='tenant',
                        created_by='admin',
                        archive_location=(
                            '{tempdir}/tenants/default_tenant/'
                            'blueprints_archives/fakecloudmore.zip'
                        ),
                        skip_execution=True,
                        blueprint_id='fakecloudmore',
                        blueprint_filename='bpfakecloudmore.yaml',
                        async_upload=True,
                    ),
                    mock.call(
                        created_at='2022-11-25T15:13:25.389Z',
                        visibility='tenant',
                        created_by='admin',
                        archive_location=(
                            '{tempdir}/tenants/default_tenant/'
                            'blueprints_archives/consumer.zip'
                        ),
                        skip_execution=True,
                        blueprint_id='consumer',
                        blueprint_filename='consumer.yaml',
                        async_upload=True,
                    ),
                ],
                'shared': [
                    mock.call(
                        created_at='2022-11-25T15:13:06.726Z',
                        visibility='global',
                        created_by='admin',
                        archive_location=(
                            '{tempdir}/tenants/shared/blueprints_archives/'
                            'shared_provider.zip'
                        ),
                        skip_execution=True,
                        blueprint_id='shared_provider',
                        blueprint_filename='provider.yaml',
                        async_upload=True,
                    ),
                ],
            },
            'sort_key': 'blueprint_id',
        },
        'update': {
            'expected': {
                'default_tenant': [
                    mock.call(
                        'fakecloud',
                        {
                            'plan': {'someplan': 'here'},
                            'requirements': {'parent_capabilities': []},
                            'state': 'uploaded',
                            'labels': [
                                {'key': 'general_usefulness',
                                 'value': 'low',
                                 'created_at': '2022-11-25T15:13:19.723Z',
                                 'created_by': 'admin'},
                                {'key': 'general_usefulness',
                                 'value': 'little',
                                 'created_at': '2022-11-25T15:13:19.723Z',
                                 'created_by': 'admin'},
                                {'key': 'cloudtype',
                                 'value': 'fakecloud',
                                 'created_at': '2022-11-25T15:13:19.723Z',
                                 'created_by': 'admin'},
                            ],
                        },
                    ),
                    mock.call(
                        'fakecloudmore',
                        {
                            'plan': {'otherplan': 'something'},
                            'state': 'uploaded',
                            'labels': [
                                {'key': 'general_usefulness',
                                 'value': 'low',
                                 'created_at': '2022-11-25T15:13:23.343Z',
                                 'created_by': 'admin'},
                                {'key': 'general_usefulness',
                                 'value': 'little',
                                 'created_at': '2022-11-25T15:13:23.343Z',
                                 'created_by': 'admin'},
                                {'key': 'cloudtype',
                                 'value': 'fakecloud',
                                 'created_at': '2022-11-25T15:13:23.343Z',
                                 'created_by': 'admin'},
                            ],
                        },
                    ),
                    mock.call(
                        'consumer',
                        {
                            'plan': {'planplan': 'theplan'},
                            'state': 'uploaded',
                            'description': 'Some dep that does a thing.\n',
                        },
                    ),
                ],
                'shared': [
                    mock.call(
                        'shared_provider',
                        {
                            'plan': {'some': 'thing'},
                            'state': 'uploaded',
                            'description': 'I believe I can fly.\n'
                        }
                    ),
                ],
            },
            'sort_key': '',
        },
    },
    'deployments': {
        'create': {
            'expected': {
                'default_tenant': [
                    mock.call(
                        created_at='2022-11-25T15:13:28.779Z',
                        visibility='tenant',
                        description='Do some stuff.\n',
                        inputs={'agent_user': 'ec2-user'},
                        groups={},
                        policy_triggers={'policy': 'stuff'},
                        policy_types={'policy': 'type'},
                        outputs={},
                        capabilities={'cap': 'something'},
                        scaling_groups={},
                        runtime_only_evaluation=False,
                        installation_status='active',
                        deployment_status='good',
                        display_name='shared_provider',
                        resource_tags={},
                        blueprint_id='shared_provider',
                        created_by='admin',
                        sub_services_status='good',
                        sub_environments_status='good',
                        sub_services_count=0,
                        sub_environments_count=0,
                        labels=[],
                        # If the b64zip file does not exist, it should be
                        # auto-populated with the empty zip
                        _workdir_zip=EMPTY_B64_ZIP,
                        deployment_id='shared_provider',
                        async_create=False,
                        workflows={'whatever': {}, 'other': {}},
                    ),
                    mock.call(
                        created_at='2022-11-25T15:13:49.658Z',
                        visibility='tenant',
                        description=None,
                        inputs={},
                        groups={},
                        policy_triggers={'policy': 'trig'},
                        policy_types={'policy': 'type2'},
                        outputs={},
                        capabilities={},
                        scaling_groups={},
                        runtime_only_evaluation=False,
                        installation_status='active',
                        deployment_status='good',
                        display_name='fakeclouddeps-123',
                        resource_tags={},
                        blueprint_id='fakecloud',
                        created_by='admin',
                        sub_services_status='in_progress',
                        sub_environments_status='requires_attention',
                        sub_services_count=1,
                        sub_environments_count=2,
                        labels=[
                            {'key': 'general_usefulness',
                             'value': 'low',
                             'created_at': '2022-11-25T15:13:51.006Z',
                             'created_by': 'admin'},
                            {'key': 'cake',
                             'value': 'untrue',
                             'created_at': '2022-11-25T15:13:51.006Z',
                             'created_by': 'admin'},
                        ],
                        _workdir_zip='There should be cake.\n',
                        deployment_id='fakeclouddeps-123',
                        async_create=False,
                        workflows={'someother': {}}
                    ),
                ],
            },
            'sort_key': 'deployment_id',
        },
    },
    'inter_deployment_dependencies': {
        'create': {
            'expected': {
                'default_tenant': [
                    mock.call(
                        _id='602b6102-e4bd-42ed-a86c-10b526d3b4c2',
                        _visibility='tenant',
                        _created_at='2023-03-02T08:38:56.080Z',
                        _created_by='admin',
                        dependency_creator=IDD_DEPENDENCY_CREATOR,
                        target_deployment_func={
                            'context':
                                {'self': 'n1_robir7'},
                            'function':
                                {'get_attribute': ['rel_target', 'dep_id']},
                        },
                        source_deployment='d3',
                        target_deployment='d1',
                        external_source=None,
                        external_target=None,
                    ),
                    mock.call(
                        _id='84c87185-71d9-447b-b1b5-4421c416bdfb',
                        _visibility='tenant',
                        _created_at='2023-03-02T08:38:56.080Z',
                        _created_by='admin',
                        dependency_creator=IDD_DEPENDENCY_CREATOR,
                        target_deployment_func={
                            'context':
                                {'self': 'n1_x4imdw'},
                            'function':
                                {'get_attribute': ['rel_target', 'dep_id']},
                        },
                        source_deployment='d3',
                        target_deployment='d2',
                        external_source=None,
                        external_target=None,
                    ),
                ]
            },
            'sort_key': '',
        },
    },
    'nodes': {
        'create_many': {
            'expected': {
                'default_tenant': [
                    # Only one call because there are no node files for the
                    # other deployment
                    mock.call(deployment_id='shared_provider',
                              nodes=[{'id': 'somenode', 'creator': 'someone'},
                                     {'id': 'othernode', 'creator': 'other'}]),
                ]
            },
            'sort_key': '',
        },
    },
    'node_instances': {
        'create_many': {
            'expected': {
                'default_tenant': [
                    # One call per dep, because we can batch upload them
                    mock.call(
                        deployment_id='shared_provider',
                        node_instances=[
                            {'id': 'vm_93pf5z', 'visibility': 'tenant',
                             'host_id': 'vm_93pf5z', 'index': 1,
                             'relationships': [],
                             'runtime_properties': {'some': 'property'},
                             'system_properties': {},
                             'scaling_groups': [],
                             'state': 'started',
                             'has_configuration_drift': False,
                             'is_status_check_ok': True,
                             'node_id': 'vm', 'creator': 'admin'},
                            {'id': 'proxy_node_t13ji', 'visibility': 'tenant',
                             'host_id': None, 'index': 1, 'relationships': [],
                             'runtime_properties': {},
                             'system_properties': {},
                             'scaling_groups': [], 'state': 'started',
                             'has_configuration_drift': False,
                             'is_status_check_ok': True,
                             'node_id': 'proxy_node', 'creator': 'admin'}
                        ],
                    ),
                ],
            },
            'sort_key': 'deployment_id',
        },
    },
    'agents': {
        'create': {
            'expected': {
                'default_tenant': [
                    mock.call(create_rabbitmq_user=True,
                              node_instance_id='vm_93pf5z',
                              ip='192.168.42.173', install_method='remote',
                              system=None, version='7.0.0-.dev1',
                              created_at='2022-11-25T15:13:35.386Z',
                              rabbitmq_exchange='vm_93pf5z',
                              created_by='admin',
                              rabbitmq_username='rabbitmq_user_vm_93pf5z',
                              visibility='tenant', rabbitmq_password='wibble',
                              state='started', name='vm_93pf5z'),
                ],
            },
            'sort_key': 'node_instance_id',
        },
    },
    'deployment_groups': {
        'put': {
            'expected': {
                'default_tenant': [
                    mock.call(created_at='2022-11-25T15:13:48.887Z',
                              visibility='tenant', description=None,
                              default_inputs={}, creation_counter=1,
                              created_by='admin',
                              deployment_ids=['fakeclouddeps-123'],
                              labels=[], group_id='fakeclouddeps',
                              blueprint_id='fakecloud'),
                    mock.call(created_at='2022-11-25T15:14:03.940Z',
                              visibility='tenant', description=None,
                              default_inputs={
                                  'source_deployment': 'shared_provider',
                                  'tenant': 'default_tenant',
                                  'path': '/home/ec2-user/somefile',
                                  'content': 'ilikecake'
                              },
                              creation_counter=1, created_by='admin',
                              deployment_ids=['consumerdeps-abc'],
                              labels=[], group_id='consumerdeps',
                              blueprint_id='consumer'),
                ],
            },
            'sort_key': 'group_id',
        },
    },
    'executions': {
        'create': {
            'expected': {
                'default_tenant': [
                    mock.call(
                        created_at='2022-11-25T15:13:17.930Z',
                        ended_at='2022-11-25T15:13:19.979Z',
                        error='',
                        parameters={
                            'blueprint_id': 'fakecloud',
                            'app_file_name': 'bpfakecloud.yaml',
                            'url': None,
                            'file_server_root': '/opt/manager/resources',
                            'marketplace_api_url': 'https://example',
                            'validate_only': False,
                            'labels': [],
                        },
                        workflow_id='upload_blueprint',
                        started_at='2022-11-25T15:13:18.858Z',
                        allow_custom_parameters=True,
                        deployment_id='',
                        created_by='admin',
                        execution_id='38b2b31c-7bde-462e-9f67-d08540e72bdd',
                        force_status='terminated',
                        dry_run=False,
                    ),
                    mock.call(
                        created_at='2022-11-25T15:13:21.583Z',
                        ended_at='2022-11-25T15:13:23.508Z',
                        error='',
                        parameters={
                            'blueprint_id': 'fakecloudmore',
                            'app_file_name': 'bpfakecloudmore.yaml',
                            'url': None,
                            'file_server_root': '/opt/manager/resources',
                            'marketplace_api_url': 'https://example',
                            'validate_only': False,
                            'labels': [],
                        },
                        workflow_id='upload_blueprint',
                        started_at='2022-11-25T15:13:22.482Z',
                        allow_custom_parameters=True,
                        deployment_id='',
                        created_by='admin',
                        execution_id='80bfb8db-6811-45ff-b01e-14a4e45673d5',
                        force_status='terminated',
                        dry_run=False,
                    ),
                ],
                'shared': [
                    mock.call(
                        created_at='2022-11-25T15:13:06.758Z',
                        ended_at='2022-11-25T15:13:12.799Z',
                        error='',
                        parameters={
                            'blueprint_id': 'shared_provider',
                            'app_file_name': 'provider.yaml',
                            'url': None,
                            'file_server_root': '/opt/manager/resources',
                            'marketplace_api_url': 'https://example',
                            'validate_only': False, 'labels': [],
                        },
                        workflow_id='upload_blueprint',
                        started_at='2022-11-25T15:13:11.492Z',
                        allow_custom_parameters=True,
                        deployment_id='',
                        created_by='admin',
                        execution_id='bdc6780d-836b-4d4c-9586-dafef3d0ef67',
                        force_status='terminated',
                        dry_run=False,
                    ),
                ],
            },
            'sort_key': 'execution_id',
        },
    },
    'tasks_graphs': {
        'create': {
            'expected': {
                'default_tenant': [
                    mock.call(
                        created_at='2022-11-25T15:14:39.191Z',
                        name='update_check_drift',
                        execution_id='38b2b31c-7bde-462e-9f67-d08540e72bdd',
                        operations=[
                            {
                                'created_at': '2022-11-25T15:14:39.191Z',
                                'id': '184e9c1a-b951-4954-a566-60dc5822453a',
                                'name': 'NOP',
                                'state': 'pending',
                                'dependencies': [],
                                'type': 'NOPLocalWorkflowTask',
                                'parameters': {
                                    'on_success': {
                                        'path': 'whatever'
                                    },
                                    'on_failure': {
                                        'path': 'someother'
                                    },
                                    'retried_task': None,
                                    'current_retries': 0,
                                    'send_task_events': True,
                                    'retry_interval': 30,
                                    'total_retries': -1,
                                    'info': None,
                                    'error': None,
                                    'containing_subgraph': None,
                                    'task_kwargs': {}
                                },
                                'manager_name': None,
                                'agent_name': None
                            },
                        ],
                        graph_id='6d4e2e5e-87aa-471b-a1e0-4bc8a48a4ec3'
                    ),
                    mock.call(
                        created_at='2022-11-25T15:14:19.203Z',
                        name='install',
                        execution_id='80bfb8db-6811-45ff-b01e-14a4e45673d5',
                        operations=[
                            {
                                'created_at': '2022-11-25T15:14:19.203Z',
                                'id': 'ff7480dc-a8dd-43d7-8b8d-82594d50e892',
                                'name': 'SendNodeEventTask',
                                'state': 'succeeded',
                                'dependencies': [
                                    '9a87b711-03cf-468c-98a1-7610d0ddbd48',
                                    '57d3eca2-73ab-4d34-afe1-47d3b929118f'
                                ],
                                'type': 'SendNodeEventTask',
                                'parameters': {
                                    'on_success': None,
                                    'on_failure': None,
                                    'retried_task': None,
                                    'current_retries': 0,
                                    'send_task_events': False,
                                    'retry_interval': 30,
                                    'total_retries': 0,
                                    'info': 'Validating stuff',
                                    'error': None,
                                    'containing_subgraph': 'somesubgraph',
                                    'task_kwargs': {},
                                },
                                'manager_name': 'i-033a355130693f2d0',
                                'agent_name': None
                            }
                        ],
                        graph_id='595734d3-1535-4894-b366-ae36e52ca27c'
                    ),
                ],
            },
            'sort_key': '',
        },
    },
    'execution_groups': {
        'create': {
            'expected': {
                'default_tenant': [
                    mock.call(created_at='2022-11-25T15:13:49.683Z',
                              id='36e2897c-c3c2-41ea-9a94-8bf43d09aaff',
                              workflow_id='create_deployment_environment',
                              concurrency=10,
                              deployment_group_id='fakeclouddeps',
                              created_by='admin',
                              executions=['exc1']),
                    mock.call(created_at='2022-11-25T15:14:04.922Z',
                              id='180524ee-a9d6-4f63-86a2-734ab6537c90',
                              workflow_id='create_deployment_environment',
                              concurrency=10,
                              deployment_group_id='consumerdeps',
                              created_by='admin',
                              executions=['anotherexec']),
                ],
            },
            'sort_key': '',
        },
    },
    'events': {
        'create': {
            'expected': {
                'default_tenant': [
                    mock.call(
                        events=[],
                        logs=[
                            {'timestamp': '2022-11-25T15:13:18.962Z',
                             'reported_timestamp': '2022-11-25T15:13:18.983Z',
                             'blueprint_id': None, 'deployment_id': None,
                             'deployment_display_name': None,
                             'workflow_id': 'upload_blueprint',
                             'error_causes': None, 'logger': 'ctx.xyz',
                             'level': 'info', 'type': 'cloudify_log',
                             'context': {'operation': None, 'source_id': None,
                                         'target_id': None, 'node_id': None},
                             'message': {'text': 'Archive uploaded'}},
                            {'timestamp': '2022-11-25T15:13:19.675Z',
                             'reported_timestamp': '2022-11-25T15:13:19.693Z',
                             'blueprint_id': None, 'deployment_id': None,
                             'deployment_display_name': None,
                             'workflow_id': 'upload_blueprint',
                             'error_causes': None,
                             'logger': 'ctx.xyz', 'level': 'info',
                             'type': 'cloudify_log',
                             'context': {'operation': None, 'source_id': None,
                                         'target_id': None, 'node_id': None},
                             'message': {'text': 'Blueprint parsed.'}},
                        ],
                        manager_name='i-033a355130693f2d0',
                        agent_name=None,
                        execution_id='38b2b31c-7bde-462e-9f67-d08540e72bdd'),
                    mock.call(
                        events=[
                            {'timestamp': '2022-11-25T15:13:22.491Z',
                             'reported_timestamp': '2022-11-25T15:13:22.515Z',
                             'blueprint_id': None, 'deployment_id': None,
                             'deployment_display_name': None,
                             'workflow_id': 'upload_blueprint',
                             'error_causes': None,
                             'event_type': 'workflow_started',
                             'operation': None, 'type': 'cloudify_event',
                             'context': {'source_id': None, 'target_id': None,
                                         'node_id': None},
                             'message': {'text': 'Starting something'}},
                        ],
                        logs=[],
                        manager_name='i-033a355130693f2d0',
                        agent_name=None,
                        execution_id='80bfb8db-6811-45ff-b01e-14a4e45673d5'),
                    mock.call(
                        events=[
                            {'timestamp': '2022-11-25T15:13:50.762Z',
                             'reported_timestamp': '2022-11-25T15:13:50.699Z',
                             'blueprint_id': None, 'deployment_id': None,
                             'deployment_display_name': None,
                             'workflow_id': None, 'error_causes': None,
                             'event_type': 'execution_state_change',
                             'operation': None, 'type': 'cloudify_event',
                             'context': {'source_id': None, 'target_id': None,
                                         'node_id': None},
                             'message': {'text': 'execution x started'}},
                        ],
                        logs=[],
                        manager_name=None,
                        agent_name=None,
                        execution_group_id=(
                            '36e2897c-c3c2-41ea-9a94-8bf43d09aaff'
                        )),
                    mock.call(
                        events=[
                            {'timestamp': '2022-11-25T15:14:05.970Z',
                             'reported_timestamp': '2022-11-25T15:14:05.946Z',
                             'blueprint_id': None, 'deployment_id': None,
                             'deployment_display_name': None,
                             'workflow_id': None, 'error_causes': None,
                             'event_type': 'execution_state_change',
                             'operation': None, 'type': 'cloudify_event',
                             'context': {'source_id': None, 'target_id': None,
                                         'node_id': None},
                             'message': {'text': 'execution 1 started'}}
                        ],
                        logs=[],
                        manager_name=None,
                        agent_name=None,
                        execution_group_id=(
                            '180524ee-a9d6-4f63-86a2-734ab6537c90'
                        )),
                ],
                'shared': [
                    mock.call(
                        events=[
                            {'timestamp': '2022-11-25T15:13:11.510Z',
                             'reported_timestamp': '2022-11-25T15:13:11.563Z',
                             'blueprint_id': None, 'deployment_id': None,
                             'deployment_display_name': None,
                             'workflow_id': 'upload_blueprint',
                             'error_causes': None,
                             'event_type': 'workflow_started',
                             'operation': None, 'type': 'cloudify_event',
                             'context': {'source_id': None, 'target_id': None,
                                         'node_id': None},
                             'message': {'text': "Start upload_execution"}},
                            {'timestamp': '2022-11-25T15:13:12.618Z',
                             'reported_timestamp': '2022-11-25T15:13:12.638Z',
                             'blueprint_id': None, 'deployment_id': None,
                             'deployment_display_name': None,
                             'workflow_id': 'upload_blueprint',
                             'error_causes': None,
                             'event_type': 'workflow_succeeded',
                             'operation': None, 'type': 'cloudify_event',
                             'context': {'source_id': None, 'target_id': None,
                                         'node_id': None},
                             'message': {'text': "Win upload_execution"}},
                        ],
                        logs=[
                            {'timestamp': '2022-11-25T15:13:11.663Z',
                             'reported_timestamp': '2022-11-25T15:13:11.777Z',
                             'blueprint_id': None, 'deployment_id': None,
                             'deployment_display_name': None,
                             'workflow_id': 'upload_blueprint',
                             'error_causes': None,
                             'logger': 'ctx.abc123',
                             'level': 'info',
                             'type': 'cloudify_log',
                             'context': {'operation': None, 'source_id': None,
                                         'target_id': None, 'node_id': None},
                             'message': {'text': 'Archive extracting...'}},
                            {'timestamp': '2022-11-25T15:13:11.871Z',
                             'reported_timestamp': '2022-11-25T15:13:11.888Z',
                             'blueprint_id': None, 'deployment_id': None,
                             'deployment_display_name': None,
                             'workflow_id': 'upload_blueprint',
                             'error_causes': None,
                             'logger': 'ctx.def456',
                             'level': 'info',
                             'type': 'cloudify_log',
                             'context': {'operation': None, 'source_id': None,
                                         'target_id': None, 'node_id': None},
                             'message': {'text': 'Blueprint parsing...'}},
                        ],
                        manager_name='i-033a355130693f2d0',
                        agent_name=None,
                        execution_id='bdc6780d-836b-4d4c-9586-dafef3d0ef67',
                    ),
                ],
            },
            'sort_key': 'manager_name',
        },
    },
    'execution_schedules': {
        'create': {
            'expected': {
                'default_tenant': [
                    mock.call(created_at='2022-11-25T15:14:26.861Z',
                              since='2022-12-09T15:14:00.000Z',
                              until=None, slip=0,
                              workflow_id='validate_agents', parameters={},
                              execution_arguments={
                                  'allow_custom_parameters': False,
                                  'force': False, 'is_dry_run': False,
                                  'wait_after_fail': 600,
                              },
                              stop_on_fail=False,
                              enabled=True,
                              deployment_id='shared_provider',
                              created_by='admin',
                              schedule_id='validate_agents',
                              rrule='RRULE:FREQ=DAILY;INTERVAL=3'),
                ],
            },
            'sort_key': '',
        },
    },
    'deployment_updates': {
        'create': {
            'expected': {
                'default_tenant': [
                    mock.call(created_at="2022-12-08T08:48:41.581Z",
                              update_id="somedepupdate",
                              visibility="tenant",
                              deployment_plan={"whatever": "goes here"},
                              deployment_update_node_instances={
                                  "stuff": "here"},
                              central_plugins_to_uninstall=None,
                              central_plugins_to_install=None,
                              deployment_update_nodes={"something": "else"},
                              modified_entity_ids=None,
                              old_inputs={},
                              inputs={},
                              state="successful",
                              runtime_only_evaluation=False,
                              deployment_id="somedeployment",
                              execution_id="thisistheendmyonlyfriend",
                              old_blueprint_id="fakecloud",
                              blueprint_id="fakecloudmore",
                              created_by="admin",
                              steps=[{"september": "sun"}, {"over": "joyed"},
                                     {"neon": "blue"}]),
                ],
            },
            'sort_key': 'id',
        },
    },
    'plugins_update': {
        'inject': {
            'expected': {
                'default_tenant': [
                    mock.call(created_at='2022-11-25T15:14:35.397Z',
                              state='successful',
                              deployments_per_tenant={
                                  'default_tenant': ['dep1', 'dep2'],
                              },
                              all_tenants=False,
                              blueprint_id='fakecloudmore',
                              temp_blueprint_id=None,
                              execution_id='someexecid',
                              created_by='admin',
                              update_id='someupdateid',
                              affected_deployments=None,
                              force=False),
                ],
            },
            'sort_key': 'update_id',
        },
    },
    'secrets_providers': {
        'create': {
            'expected': {
                'other': [
                    mock.call(_type='something',
                              name='whatever'),
                ],
            },
            'sort_key': 'name',
        },
    },
}


def _get_rest_client(tenant=None):
    mock_client = mock.Mock(spec={'manager'} | EXPECTED_CALLS.keys())

    mock_client.manager = mock.Mock(spec={'get_version'})
    mock_client.manager.get_version = mock.Mock(
        return_value={'version': '7.0.0.'})

    for group in EXPECTED_CALLS:
        mock_methods = mock.Mock(spec=EXPECTED_CALLS[group].keys())
        for call in EXPECTED_CALLS[group]:
            if group == 'permissions' and call == 'list':
                return_value = ListResponse(
                    [{'role': 'sys_admin', 'permission': 'getting_started'}],
                    {'pagination': {'total': 0, 'size': 1000}})
            else:
                return_value = {}
            mock_call = mock.Mock(return_value=return_value)
            setattr(mock_methods, call, mock_call)
        setattr(mock_client, group, mock_methods)

    return mock_client


@pytest.fixture
def mock_get_client():
    with mock.patch(
        'cloudify_system_workflows.snapshots.snapshot_restore'
        '.get_rest_client',
        side_effect=_get_rest_client,
    ):
        yield


@pytest.fixture
def mock_get_composer_client():
    class MockComposerClient():
        def get_snapshots(self, dump_type):
            pass

        def put_snapshot(self, dump_type, file_path, expected_status=201):
            pass

        def put_blueprints_snapshot(self,
                                    metadata_file_path,
                                    snapshot_file_path,
                                    expected_status=201):
            pass

    with mock.patch(
        'cloudify_system_workflows.snapshots.utils'
        '.get_composer_client',
        side_effect=MockComposerClient,
    ) as client:
        yield client


@pytest.fixture
def mock_ctx():
    with mock.patch(
        'cloudify_system_workflows.snapshots.snapshot_restore'
        '.ctx',
        # Don't try to magicmock the context or we need a context
        new=mock.Mock(),
    ):
        yield


@pytest.fixture
def mock_manager_restoring():
    with mock.patch(
        'cloudify_system_workflows.snapshots.snapshot_restore'
        '.SnapshotRestore._mark_manager_restoring',
    ) as mock_mgr_restoring:
        yield mock_mgr_restoring


@pytest.fixture
def mock_manager_finished_restoring():
    with mock.patch(
        'cloudify_system_workflows.snapshots.snapshot_restore'
        '.SnapshotRestore._mark_manager_finished_restoring',
    ) as mock_mgr_finished_restoring:
        yield mock_mgr_finished_restoring


@dataclass
class FakeZipFileEntry:
    _is_dir: bool
    filename: str

    def is_dir(self):
        return self._is_dir


class FakeZipFile:
    def __init__(self, snapshot_path, _mode):
        self._snapshot_path = snapshot_path
        self._form_filelist()

    def _form_filelist(self):
        self._filelist = []
        for item in os.walk(self._snapshot_path):
            base, dirs, files = item
            base = base[len(self._snapshot_path) + 1:]

            for path in dirs:
                self._filelist.append(FakeZipFileEntry(
                    _is_dir=True, filename=os.path.join(base, path),
                ))
            for path in files:
                self._filelist.append(FakeZipFileEntry(
                    _is_dir=False, filename=os.path.join(base, path),
                ))

    def __enter__(self):
        return self

    def extract(self, path, dest):
        full_src = os.path.join(self._snapshot_path, path)
        full_dest = os.path.join(dest, path)
        dest_dir = os.path.dirname(full_dest)
        os.makedirs(dest_dir, exist_ok=True)
        shutil.copy(full_src, full_dest)

    @property
    def filelist(self):
        return self._filelist

    def __exit__(self, type, value, traceback):
        pass


@pytest.fixture
def mock_zipfile():
    with mock.patch(
        'cloudify_system_workflows.snapshots.snapshot_restore'
        '.ZipFile',
        new=FakeZipFile,
    ):
        yield


@pytest.fixture
def mock_mkdir():
    with mock.patch(
        'cloudify_system_workflows.snapshots.snapshot_restore'
        '.tempfile.mkdtemp',
    ) as mock_dtemp:
        yield mock_dtemp


@pytest.fixture
def mock_no_rmtree():
    with mock.patch(
        'cloudify_system_workflows.snapshots.snapshot_restore'
        '.shutil.rmtree',
    ):
        yield


@pytest.fixture
def mock_unlink():
    with mock.patch(
        'cloudify_system_workflows.snapshots.snapshot_restore'
        '.os.unlink',
    ) as unlink:
        yield unlink


def test_restore_snapshot(mock_ctx, mock_get_client, mock_zipfile,
                          mock_manager_restoring, mock_mkdir,
                          mock_no_rmtree, mock_unlink,
                          mock_get_composer_client,
                          mock_manager_finished_restoring):
    _test_restore('testsnapshot', 'snapshot_contents', EXPECTED_CALLS,
                  TENANTS, mock_mkdir, mock_manager_restoring,
                  mock_manager_finished_restoring, mock_unlink)


def test_restore_partial_snapshot(mock_ctx, mock_get_client, mock_zipfile,
                                  mock_manager_restoring, mock_mkdir,
                                  mock_no_rmtree, mock_unlink,
                                  mock_get_composer_client,
                                  mock_manager_finished_restoring):
    _test_restore('testpartialsnapshot', 'partial_snapshot_contents',
                  PARTIAL_SNAP_EXPECTED_CALLS, PARTIAL_TENANTS, mock_mkdir,
                  mock_manager_restoring, mock_manager_finished_restoring,
                  mock_unlink)


def _test_restore(snap_id, snap_contents_dir, calls, tenants,
                  mock_mkdir, mock_manager_restoring,
                  mock_manager_finished_restoring, mock_unlink):
    tempdir = mkdtemp('-test-snap-restore-data')
    mock_mkdir.return_value = tempdir

    try:
        snap_res = SnapshotRestore(
            snapshot_id=snap_id,
            config={
                'snapshot_restore_threads': 0,  # Not used yet by new snap res
                'file_server_root': tempdir,
            },
            # These flags are all required until old snapshots are gone
            # entirely, but are not used for new snapshots
            force=None,
            timeout=None,
            premium_enabled=None,
            user_is_bootstrap_admin=None,
            restore_certificates=None,
            no_reboot=None,
        )

        snap_res._get_snapshot_path = mock.Mock(
            return_value=os.path.join(
                os.path.dirname(__file__), snap_contents_dir,
            )
        )

        snap_res._validate_snapshot = mock.Mock(side_effect=AssertionError(
            'Attempted to use old snapshot restore approach'))
        snap_res.restore()

        mock_manager_restoring.assert_called_once_with()
        _assert_mgmt_restores(snap_res._client, calls)
        _assert_tenant_restores(snap_res._tenant_clients, tempdir, calls,
                                tenants)
        mock_manager_finished_restoring.assert_called_once_with()
        _assert_cleanup(FakeZipFile(snap_res._get_snapshot_path(), 'r'),
                        tempdir,
                        mock_unlink)
    finally:
        shutil.rmtree(tempdir)


def _assert_cleanup(zipfile, tempdir, unlink):
    # The actual unlinks should happen after each file is extracted, but we
    # can't trivially check that, so we'll make sure each file is unlinked and
    # trust that the unlinking is logically timed in the snap res itself
    expected_deletions = []
    for filename in zipfile.filelist:
        if filename.is_dir():
            continue
        else:
            path = os.path.join(tempdir, filename.filename)
            expected_deletions.append(path)
    unlink.assert_has_calls([mock.call(path) for path in expected_deletions],
                            any_order=True)


def _assert_mgmt_restores(client, calls):
    _check_calls(client, None, None, calls)


def _assert_tenant_restores(clients, tempdir, calls, tenants):
    assert tenants == set(clients)

    for tenant in tenants:
        _check_calls(clients[tenant], tenant, tempdir, calls)


def _sort_events(events_call_list):
    for call in events_call_list:
        call.kwargs['logs'] = sorted([
            json.dumps(item, sort_keys=True)
            for item in call.kwargs['logs']
        ])
        call.kwargs['events'] = sorted([
            json.dumps(item, sort_keys=True)
            for item in call.kwargs['events']
        ])

    return sorted(events_call_list,
                  key=lambda x: json.dumps(x.kwargs, sort_keys=True))


def _check_calls(client, tenant, tempdir, calls):
    for group in calls:
        group_client = getattr(client, group)
        for call in calls[group]:
            expected_calls = calls[group][call]['expected'].get(
                tenant, {})
            call_client = getattr(group_client, call)
            if not any([expected_calls, call_client.call_args_list]):
                continue

            if group == 'events':
                expected = _sort_events(expected_calls)
                results = _sort_events(call_client.call_args_list)
            else:
                sort_key = calls[group][call]['sort_key']
                expected = sorted(expected_calls,
                                  key=lambda x: getattr(x, sort_key))
                results = sorted(call_client.call_args_list,
                                 key=lambda x: getattr(x, sort_key))

            if group == 'plugins' and call == 'upload':
                for item in expected:
                    item.kwargs['plugin_path'] = item.kwargs[
                        'plugin_path'].format(tempdir=tempdir)
            elif group == 'blueprints' and call == 'publish_archive':
                for item in expected:
                    item.kwargs['archive_location'] = item.kwargs[
                        'archive_location'].format(tempdir=tempdir)

            if tenant:
                print(f'Checking calls to {group}.{call} for {tenant}')
            else:
                print(f'Checking mgmt calls to {group}.{call}')
            assert results == expected
