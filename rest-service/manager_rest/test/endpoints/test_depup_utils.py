import unittest

from manager_rest.deployment_update import utils


class DeploymentUpdateTestCase(unittest.TestCase):

    def test_traverse_object(self):
        object_to_traverse = {
            'nodes': {
                'n1': 1,
                'n2': ['l2', {'inner': [3]}]
            }
        }

        # assert the value returned from a dictionary traverse
        self.assertEqual(
                utils.traverse_object(object_to_traverse, ['nodes', 'n1']), 1)

        # assert access to inner list
        self.assertEqual(utils.traverse_object(object_to_traverse,
                                               ['nodes', 'n2', '[0]']), 'l2')

        # assert access to a dict within a list within a dict
        self.assertEqual(utils.traverse_object(object_to_traverse,
                         ['nodes', 'n2', '[1]', 'inner', '[0]']), 3)

        self.assertDictEqual(object_to_traverse,
                             utils.traverse_object(object_to_traverse,
                                                   []))

    def test_create_dict_with_value(self):
        dict_breadcrumb = ['super_level', 'mid_level', 'sub_level']

        self.assertDictEqual({'super_level': {
            'mid_level': {
                'sub_level': 'value'
            }
        }}, utils.create_dict(dict_breadcrumb, 'value'))

    def test_create_dict_with_no_value(self):
        dict_breadcrumb = ['super_level', 'mid_level', 'sub_level', 'value']

        self.assertDictEqual({'super_level': {
            'mid_level': {
                'sub_level': 'value'
            }
        }}, utils.create_dict(dict_breadcrumb))

    def test_get_raw_node(self):

        blueprint_to_test = {
            'nodes': [{'id': 1, 'name': 'n1'},  {'id': 2, 'name': 'n2'}]
        }

        # assert the right id is returned on existing node
        self.assertDictEqual(utils.get_raw_node(blueprint_to_test, 1),
                             {'id': 1, 'name': 'n1'})

        # assert no value is returned on non existing id
        self.assertEqual(len(utils.get_raw_node(blueprint_to_test, 3)), 0)

        # assert nothing is return on invalid blueprint
        self.assertEqual(len(utils.get_raw_node({'no_nodes': 1}, 1)), 0)

    def test_parse_index(self):
        self.assertEqual(utils.parse_index('[15]'), 15)
        self.assertFalse(utils.parse_index('[abc]'))
        self.assertFalse(utils.parse_index('[1a]'))
        self.assertFalse(utils.parse_index('~~[]'))

    def test_check_is_int(self):
        self.assertTrue(utils.check_is_int('123'))
        self.assertFalse(utils.check_is_int('abc'))
        self.assertFalse(utils.check_is_int('ab12'))
