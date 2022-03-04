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

    def get_deployments(self, deployment_id,
                        filter_id=None,
                        labels=None,
                        tenants=None,
                        display_name_specs=None):
        kwargs = {}
        if filter_id:
            kwargs['filter_id'] = filter_id
        filter_rules = []
        if labels:
            filter_rules.extend(
                {"key": list(label.keys())[0],
                 "values": [list(label.values())[0]],
                 "operator": "any_of",
                 "type": "label"}
                for label in labels
            )
        if tenants:
            filter_rules.append(
                {"key": "tenant_name",
                 "values": tenants,
                 "operator": "any_of",
                 "type": "attribute"}
            )
        if display_name_specs:
            for op, spec in display_name_specs.items():
                filter_rules.append(
                    {"key": "display_name",
                     "values": [spec],
                     "operator": "any_of" if op == "equals_to" else op,
                     "type": "attribute"})
        if filter_rules:
            kwargs['filter_rules'] = filter_rules
        return self.client.deployments.list(_search=deployment_id,
                                            _include=['id'],
                                            _get_all_results=True,
                                            **kwargs)

    def get_blueprints(self, blueprint_id,
                       filter_id=None,
                       labels=None,
                       tenants=None,
                       id_specs=None):
        kwargs = {}
        if filter_id:
            kwargs['filter_id'] = filter_id
        filter_rules = []
        if labels:
            filter_rules.extend(
                {"key": list(label.keys())[0],
                 "values": [list(label.values())[0]],
                 "operator": "any_of",
                 "type": "label"}
                for label in labels
            )
        if tenants:
            filter_rules.append(
                {"key": "tenant_name",
                 "values": tenants,
                 "operator": "any_of",
                 "type": "attribute"}
            )
        if id_specs:
            for op, spec in id_specs.items():
                filter_rules.append(
                    {"key": "id",
                     "values": [spec],
                     "operator": "any_of" if op == "equals_to" else op,
                     "type": "attribute"})
        if filter_rules:
            kwargs['filter_rules'] = filter_rules
        return self.client.blueprints.list(_search=blueprint_id,
                                           _include=['id'],
                                           _get_all_results=True,
                                           **kwargs)

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
