
class DeploymentUpdateEnumBase(object):

    class __metaclass__(type):
        def __iter__(cls):
            for attr, value in cls.__dict__.iteritems():
                if not (callable(value) or attr.startswith('__')):
                    yield value

        def __setattr__(cls, key, value):
            pass


class DeploymentUpdateEntityTypes(DeploymentUpdateEnumBase):
    NODE = 'node'
    RELATIONSHIP = 'relationship'
    PROPERTY = 'property'


class DeploymentUpdateOperation(DeploymentUpdateEnumBase):
    ADD = 'add'
    REMOVE = 'remove'
    MODIFY = 'modify'


class DeploymentUpdateState(DeploymentUpdateEnumBase):
    COMMITTED = 'committed'
    COMMITTING = 'committing'
    STAGED = 'staged'
    REVERTED = 'reverted'
    FAILED = 'failed'

    STARTED = 'started'
    FINISHED = 'finished'
    ROLLEDBACK = 'rolledback'


class DeploymentUpdateChangeTypes(DeploymentUpdateEnumBase):
    ADDED_AND_RELATED = 'added_and_related'
    EXTENDED_AND_RELATED = 'extended_and_related'
    REDUCED_AND_RELATED = 'reduced_and_related'
    REMOVED_AND_RELATED = 'removed_and_related'

    AFFECTED = 'affected'
    RELATED = 'related'

ENTITY_TYPES = DeploymentUpdateEntityTypes
OPERATIONS = DeploymentUpdateOperation
STATE = DeploymentUpdateState
CHANGE_TYPE = DeploymentUpdateChangeTypes

RELATIONSHIP_SEPARATOR = '-'
PATH_SEPARATOR = ':'
