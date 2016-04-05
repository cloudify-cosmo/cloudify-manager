import copy

from constants import ENTITY_TYPES, PATH_SEPARATOR


def pluralize(input):
    if input[-1] == 'y':
        return '{0}ies'.format(input[:-1])
    else:
        return '{0}s'.format(input)


def extract_ids(node_instances, key='id'):
    if node_instances:
        return [instance[key]
                if isinstance(instance, dict) else getattr(instance, key)
                for instance in node_instances]
    else:
        return []


class ModifiedEntitiesDict(object):

    def __init__(self):
        self.modified_entity_ids = \
            {entity_type: [] for entity_type in ENTITY_TYPES}

    def __setitem__(self, entity_type, entity_id):
        self.modified_entity_ids[entity_type].append(entity_id)

    def __getitem__(self, entity_type):
        return self.modified_entity_ids[entity_type]

    def __iter__(self):
        return iter(self.modified_entity_ids)

    def to_dict(self):

        relationships = {}
        for s_id, t_id in \
                self.modified_entity_ids[ENTITY_TYPES.RELATIONSHIP]:
            if s_id in relationships:
                relationships[s_id].append(t_id)
            else:
                relationships[s_id] = [t_id]

        modified_entities_to_return = copy.deepcopy(self.modified_entity_ids)
        modified_entities_to_return[ENTITY_TYPES.RELATIONSHIP] = \
            relationships

        return modified_entities_to_return


def traverse_object(obj, path):
    """
    Traverses an object constructed out of dicts and lists.
    :param obj: the object to traverse
    :param path: the path on which to traverse, while list indices surrounded
    by [x]
    :return: the objectr at the end of the path
    """

    if not path:
        return obj
    current_key = path[0]
    if current_key in obj:
        return traverse_object(obj[path[0]], path[1:])
    elif current_key.startswith('[') and current_key.endswith(']'):
        return traverse_object(obj[int(current_key[1:-1])], path[1:])
    else:
        return {}


def create_dict(path, value=None):
    if value:
        if not path:
            return value
    elif len(path) == 1:
        return path[0]
    return {path[0]: create_dict(path[1:], value)}


def get_entity_keys(entity_id):
    return entity_id.split(PATH_SEPARATOR)


def get_raw_node(blueprint, node_id):
    nodes = [n for n in blueprint['nodes']
             if n['id'] == node_id]
    return nodes[0] if nodes else {}
