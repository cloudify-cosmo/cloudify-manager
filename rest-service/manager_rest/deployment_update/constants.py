from collections import namedtuple


DeploymentUpdateEntityTypes = namedtuple('DeploymentUpdateEntityTypes',
                                         ['NODE',
                                          'RELATIONSHIP',
                                          'PROPERTY',
                                          'OPERATION',
                                          'WORKFLOW',
                                          'OUTPUT',
                                          'DESCRIPTION'])

DeploymentUpdateActionTypes = namedtuple('DeploymentUpdateActionTypes',
                                         ['ADD', 'REMOVE', 'MODIFY'])

DeploymentUpdateStates = namedtuple('DeploymentUpdateStates',
                                    ['COMMITTED',
                                     'COMMITTING',
                                     'STAGED',
                                     'REVERTED',
                                     'FAILED',
                                     'STARTED',
                                     'FINISHED',
                                     'ROLLEDBACK'])

DeploymentUpdateNodeModificationTypes = \
    namedtuple('DeploymentUpdateNodeModificationTypes',
               ['ADDED_AND_RELATED',
                'EXTENDED_AND_RELATED',
                'REDUCED_AND_RELATED',
                'REMOVED_AND_RELATED',
                'AFFECTED',
                'RELATED'])

DeploymentUpdatePhases = namedtuple('DeploymentUpdatePhases',
                                    ['INITIAL', 'FINAL'])

ENTITY_TYPES = DeploymentUpdateEntityTypes(NODE='node',
                                           RELATIONSHIP='relationship',
                                           PROPERTY='property',
                                           OPERATION='operation',
                                           WORKFLOW='workflow',
                                           OUTPUT='output',
                                           DESCRIPTION='description')
ACTION_TYPES = DeploymentUpdateActionTypes(ADD='add',
                                           REMOVE='remove',
                                           MODIFY='modify')
STATES = DeploymentUpdateStates(COMMITTED='committed',
                                COMMITTING='committing',
                                STAGED='staged',
                                REVERTED='reverted',
                                FAILED='failed',
                                STARTED='started',
                                FINISHED='finished',
                                ROLLEDBACK='rolledback')
NODE_MOD_TYPES = DeploymentUpdateNodeModificationTypes(
        ADDED_AND_RELATED='added_and_related',
        EXTENDED_AND_RELATED='extended_and_related',
        REDUCED_AND_RELATED='reduced_and_related',
        REMOVED_AND_RELATED='removed_and_related',
        AFFECTED='affected',
        RELATED='related')

PHASES = DeploymentUpdatePhases(INITIAL='initiate', FINAL='finalize')

PATH_SEPARATOR = ':'
DEFAULT_DEPLOYMENT_UPDATE_WORKFLOW = 'update'
