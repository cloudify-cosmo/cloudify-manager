from collections import defaultdict

from cloudify.exceptions import NonRecoverableError


class GetValuesWithRest:
    def __init__(self, client):
        self.client = client

    def get(self, data_type, value, **kwargs):
        if data_type == 'blueprint_id':
            return {b.id for b in self.get_blueprints(value, **kwargs)}
        elif data_type == 'deployment_id':
            return {d.id for d in self.get_deployments(value, **kwargs)}
        elif data_type == 'secret_key':
            return {s.key for s in self.get_secrets(value, **kwargs)}
        elif data_type == 'capability_value':
            return {cap_details['value']
                    for dep_cap in self.get_capability_values(value, **kwargs)
                    for cap in dep_cap['capabilities']
                    for cap_details in cap.values()}
        elif data_type == 'node_template':
            return {n.id for n in self.get_nodes(value, **kwargs)}
        raise NotImplementedError("Getter function not defined for "
                                  f"data type '{data_type}'")

    def get_blueprints(self, blueprint_id, **kwargs):
        return self.client.blueprints.list(_search=blueprint_id,
                                           _include=['id'],
                                           _get_all_results=True,
                                           constraints=kwargs)

    def get_deployments(self, deployment_id, **kwargs):
        return self.client.deployments.list(_search=deployment_id,
                                            _include=['id'],
                                            _get_all_results=True,
                                            constraints=kwargs)

    def get_secrets(self, secret_key, **kwargs):
        return self.client.secrets.list(_search=secret_key,
                                        _include=['key'],
                                        _get_all_results=True,
                                        constraints=kwargs)

    def get_capability_values(self, capability_value, **kwargs):
        try:
            deployment_id = kwargs.pop('deployment_id')
        except KeyError:
            raise NonRecoverableError(
                "You should provide 'deployment_id' when getting capability "
                "values.  Make sure you have `deployment_id` constraint "
                "declared for your 'capability_value' parameter.")
        return self.client.deployments.capabilities.list(
            deployment_id,
            _search=capability_value,
            _get_all_results=True,
            constraints=kwargs)

    def get_nodes(self, node_id, **kwargs):
        return self.client.nodes.list(_search=node_id,
                                      _include=['id'],
                                      _get_all_results=True,
                                      constraints=kwargs)


def get_instance_ids_by_node_ids(client, node_ids):
    ni_ids = defaultdict(set)
    offset = 0
    ni_num = 0
    while True:
        nis = client.node_instances.list(node_id=node_ids, _offset=offset)
        for ni in nis:
            ni_ids[ni['node_id']].add(ni['id'])
        ni_num += len(nis)
        if ni_num < nis.metadata.pagination.total:
            offset += nis.metadata.pagination.size
        else:
            break
    return ni_ids
