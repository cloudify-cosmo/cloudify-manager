class DeploymentUpdateEnums(object):

    class __metaclass__(type):
        def __iter__(cls):
            for attr, value in cls.__dict__.iteritems():
                if not (callable(value) or attr.startswith('__')):
                    yield value

        def __setattr__(cls, key, value):
            pass


class DeploymentUpdateEntityTypes(DeploymentUpdateEnums):
    NODE = 'node'
    RELATIONSHIP = 'relationship'


class DeploymentUpdateOperation(DeploymentUpdateEnums):
    ADD = 'add'
    REMOVE = 'remove'


class DeploymentUpdateState(DeploymentUpdateEnums):
    COMMITTED = 'committed'
    COMMITTING = 'committing'
    STAGED = 'staged'
    REVERTED = 'reverted'
    FAILED = 'failed'

    STARTED = 'started'
    FINISHED = 'finished'
    ROLLEDBACK = 'rolledback'


class DeploymentUpdateChangeTypes(DeploymentUpdateEnums):
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
