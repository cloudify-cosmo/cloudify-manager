import json
import sys

from cloudify.workflows import ctx


def test_parameter(name, value):
    assert value is not None
    print("Tested parameter '{0}' is {1}".format(name, value))

    node = ctx.get_node('test_node')
    if not node:
        return
    for ni in node.instances:
        rp = ni.runtime_properties
        rp.update({'tested': True, name: value})
        ctx.update_node_instance(
            ni.id,
            runtime_properties=rp,
            version=ni.version,
        )


if __name__ == '__main__':
    with open("{0}/input.json".format(sys.argv[1]), 'r') as fh:
        data = json.load(fh)
    parameters = data.get('kwargs', {})
    expected_parameters = parameters.pop('to_be_tested')
    for k, v in parameters.items():
        if k in expected_parameters:
            test_parameter(k, v)
            expected_parameters.remove(k)
    if expected_parameters:
        raise Exception("These parameters were not tested: {0}"
                        .format(expected_parameters))
