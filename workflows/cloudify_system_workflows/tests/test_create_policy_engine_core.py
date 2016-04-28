#########
# Copyright (c) 2014 GigaSpaces Technologies Ltd. All rights reserved
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


from unittest import TestCase
from cloudify_system_workflows.deployment_environment import (
    _should_create_policy_engine_core)


class TestCreatingRiemannCore(TestCase):
    """Test deciding whether to create a policy engine core

    A riemann core should only be created when there is any group, which
    is mapped to a policy which is defined in policy_types.
    """

    def test_no_groups(self):
        "Policy engine is not needed when there are no groups defined"
        config = {
            'groups': {},
            'policy_types': {'policy1': {'source': 'foo.clj'}},
            'policy_triggers': {'trigger1': {'source': 'bar.clj'}}
        }
        self.assertFalse(_should_create_policy_engine_core(config))

    def test_empty_group(self):
        "Policy engine is not needed when no group defines policies"
        config = {
            'groups': {'group1': {'policies': {}}},
            'policy_types': {'policy1': {'source': 'foo.clj'}},
            'policy_triggers': {'trigger1': {'source': 'bar.clj'}}
        }
        self.assertFalse(_should_create_policy_engine_core(config))

    def test_group_with_no_triggers(self):
        """Create the policy engine even if no policy declares any triggers

        A policy type could potentially run any code with side effects,
        so we need to make sure it runs even if there's no triggers for it.
        """
        config = {
            'groups': {
                'group1': {
                    'policies': {
                        'some_policy': {
                            'type': 'policy1',
                            'triggers': {}
                        }
                    }
                },
            },
            'policy_types': {'policy1': {'source': 'foo.clj'}},
            'policy_triggers': {'trigger1': {'source': 'bar.clj'}}
        }
        self.assertTrue(_should_create_policy_engine_core(config))

    def test_group_with_undefined_triggers(self):
        """Create the policy engine even when triggers are undefined"""
        config = {
            'groups': {
                'group1': {
                    'policies': {
                        'some_policy': {
                            'type': 'policy1',
                            'triggers': {
                                'some_trigger': {
                                    'type': 'nonexistent'
                                }
                            }
                        }
                    }
                },
            },
            'policy_types': {'policy1': {'source': 'foo.clj'}},
            'policy_triggers': {'trigger1': {'source': 'bar.clj'}}
        }
        self.assertTrue(_should_create_policy_engine_core(config))

    def test_group_with_defined_policies(self):
        "Run the policy engine when a group declares types and triggers"
        config = {
            'groups': {
                'group1': {
                    'policies': {
                        'some_policy': {
                            'type': 'policy1',
                            'triggers': {
                                'some_trigger': {
                                    'type': 'trigger1'
                                }
                            }
                        }
                    }
                },
            },
            'policy_types': {'policy1': {'source': 'foo.clj'}},
            'policy_triggers': {'trigger1': {'source': 'bar.clj'}}
        }
        self.assertTrue(_should_create_policy_engine_core(config))
