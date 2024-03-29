from collections import OrderedDict

from manager_rest.storage.models_base import is_orm_attribute


def get_joins(model_class, columns):
    """Get a list of all the attributes on which we need to join

    :param columns: A set of all columns involved in the query
    """
    # Using an ordered dict because the order of the joins is important
    joins = OrderedDict()
    for column_name in columns:
        column = getattr(model_class, column_name, None)
        if column is None:
            # This is some sort of derived thing like tenant_roles in User
            continue
        while not is_orm_attribute(column):
            if not hasattr(column, 'local_attr'):
                # This is a property or similar, not a real column
                break
            join_attr = column.local_attr

            # This is a hack, to deal with the fact that SQLA doesn't
            # fully support doing something like: `if join_attr in joins`,
            # because some SQLA elements have their own comparators
            join_attr_name = str(join_attr)
            if join_attr_name not in joins:
                joins[join_attr_name] = join_attr
            column = column.remote_attr
    return joins.values()
