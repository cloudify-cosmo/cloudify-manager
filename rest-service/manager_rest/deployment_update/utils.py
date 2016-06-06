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

    def to_dict(self, include_rel_order=False):
        """
        Relationship entity ids support both order manipulation and
        adding/removing relationships. Thus, t_id could be both target id
        (for add/remove relationships), and (source_index, target_index)
        for order manipulation.  In order to get the order you should pass
        the include_rel_order flag,  and the dict returned will hold these
        changes under rel_order_key.

        :param include_rel_order: whether to extract the changes.
        :return: dict of modified entity ids.
        """

        relationships = {}
        rel_order = {}
        for s_id, t_id in self.modified_entity_ids[ENTITY_TYPES.RELATIONSHIP]:
            if isinstance(t_id, tuple):
                if include_rel_order:
                    if s_id in rel_order:
                        rel_order[s_id].append(t_id)
                    else:
                        rel_order[s_id] = [t_id]
            else:
                if s_id in relationships:
                    relationships[s_id].append(t_id)
                else:
                    relationships[s_id] = [t_id]

        modified_entities_to_return = copy.deepcopy(self.modified_entity_ids)
        modified_entities_to_return[ENTITY_TYPES.RELATIONSHIP] = \
            relationships
        if include_rel_order:
            modified_entities_to_return['rel_mappings'] = rel_order

        return modified_entities_to_return


def traverse_object(obj, breadcrumbs):
    """
    Traverses an object constructed out of dicts and lists.
    :param obj: the object to traverse
    :param breadcrumbs: the breadcrumbs on which to traverse, while list
    indices surrounded
    by [x]
    :return: the object at the end of the breadcrumbs
    """

    if not breadcrumbs:
        return obj
    current_key = breadcrumbs[0]

    if isinstance(obj, dict):
        if current_key in obj:
            return traverse_object(obj[breadcrumbs[0]], breadcrumbs[1:])
    elif isinstance(obj, list):
        index = parse_index(current_key)
        if index is not None and len(obj) >= index:
            return traverse_object(obj[index], breadcrumbs[1:])
    else:
        return None


def create_dict(breadcrumbs, value=None):
    """
    Created a dict out of the breadcrumbs in a recursive manner.
    each entry in the breadcrumb should be a valid dictionary key.
    If value is None, the last string within' the breadcrumbs becomes the
    final value.
    :param breadcrumbs:
    :param value:
    :return:
    """
    if value is not None:
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
        return None


def parse_index(s):
    return parse_int(s[1:-1])


def index_to_str(index):
    if check_is_int(index):
        return '[{0}]'.format(index)
