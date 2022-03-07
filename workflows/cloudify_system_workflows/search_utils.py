from collections import defaultdict


class GetEntitiesWithRest:
    def __init__(self, client):
        self.client = client

    def get(self, data_type, entity_id, **kwargs):
        if data_type == 'blueprint_id':
            return self.get_blueprints(entity_id, **kwargs)
        elif data_type == 'deployment_id':
            return self.get_deployments(entity_id, **kwargs)
        elif data_type == 'capability_value':
            return self.get_capability_value(entity_id, **kwargs)
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

    def get_capability_value(self, id, **kwargs):
        raise NotImplementedError('get_capability_value not implemented')


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
