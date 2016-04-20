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


def traverse_object(obj, breadcrumb):
    """
    Traverses an object constructed out of dicts and lists.
    :param obj: the object to traverse
    :param breadcrumb: the breadcrumb on which to traverse, while list indices
    surrounded
    by [x]
    :return: the object at the end of the breadcrumb
    """

    if not breadcrumb:
        return obj
    current_key = breadcrumb[0]
    if current_key in obj:
        return traverse_object(obj[breadcrumb[0]], breadcrumb[1:])
    elif current_key.startswith('[') and current_key.endswith(']'):
        return traverse_object(obj[int(current_key[1:-1])], breadcrumb[1:])
    else:
        return {}


def create_dict(breadcrumbs, value=None):
    """
    Created a dict out of the breadcrumbs in a recursive manner.
    each entry in the breadcrumb should be a valid dictionary key.
    :param breadcrumbs:
    :param value:
    :return:
    """
    if value:
        if not breadcrumbs:
            return value
    elif len(breadcrumbs) == 1:
        return breadcrumbs[0]
    return {breadcrumbs[0]: create_dict(breadcrumbs[1:], value)}


def get_entity_keys(entity_id):
    return entity_id.split(PATH_SEPARATOR)


def get_raw_node(blueprint, node_id):
    nodes = [n for n in blueprint.get('nodes', []) if n['id'] == node_id]
    return nodes[0] if nodes else {}


def check_is_int(s):
    try:
        int(s)
    except ValueError:
        return False

    return True


def parse_int(s):
    if check_is_int(s):
        return int(s)
    else:
        return False


def parse_index(s):
    return parse_int(s[1:-1])


def index_to_str(index):
    if check_is_int(index):
        return '[{0}]'.format(index)
