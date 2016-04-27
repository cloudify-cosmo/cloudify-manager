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
    OPERATION = 'operation'


class DeploymentUpdateActionType(DeploymentUpdateEnumBase):
    ADD = 'add'
    REMOVE = 'remove'
    MODIFY = 'modify'


class DeploymentUpdateStateType(DeploymentUpdateEnumBase):
    COMMITTED = 'committed'
    COMMITTING = 'committing'
    STAGED = 'staged'
    REVERTED = 'reverted'
    FAILED = 'failed'

    STARTED = 'started'
    FINISHED = 'finished'
    ROLLEDBACK = 'rolledback'


class DeploymentUpdateNodeModificationTypes(DeploymentUpdateEnumBase):
    ADDED_AND_RELATED = 'added_and_related'
    EXTENDED_AND_RELATED = 'extended_and_related'
    REDUCED_AND_RELATED = 'reduced_and_related'
    REMOVED_AND_RELATED = 'removed_and_related'

    AFFECTED = 'affected'
    RELATED = 'related'

ENTITY_TYPES = DeploymentUpdateEntityTypes
ACTION_TYPES = DeploymentUpdateActionType
STATES = DeploymentUpdateStateType
NODE_MOD_TYPES = DeploymentUpdateNodeModificationTypes

PATH_SEPARATOR = ':'
