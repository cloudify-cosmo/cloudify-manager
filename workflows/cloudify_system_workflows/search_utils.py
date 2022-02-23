def get_deployments_with_rest(client,
                              deployment_id,
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
    return client.deployments.list(_search=deployment_id,
                                   _include=['id'],
                                   _get_all_results=True,
                                   **kwargs)


def get_blueprints_with_rest(client,
                             blueprint_id,
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
    return client.blueprints.list(_search=blueprint_id,
                                  _include=['id'],
                                  _get_all_results=True,
                                  **kwargs)
