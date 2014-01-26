from os import path
import shutil


def copy_resources(file_server_root):

    # build orchestrator dir
    orchestrator_resources = path.abspath(__file__)
    for i in range(3):
        orchestrator_resources = path.dirname(orchestrator_resources)
    # shaky workaround intellij 'out' folder
    if not path.isdir(path.join(orchestrator_resources, 'orchestrator')):
        for i in range(2):
            orchestrator_resources = path.dirname(orchestrator_resources)
    orchestrator_resources = path.join(orchestrator_resources,
                                       'orchestrator/src/main/resources')
    # resources for dsl parser
    cloudify_resources = path.join(orchestrator_resources, 'cloudify')
    shutil.copytree(cloudify_resources, path.join(file_server_root,
                                                  'cloudify'))

    alias_mapping_resource = path.join(orchestrator_resources,
                                       'org/cloudifysource/cosmo/dsl'
                                       '/alias-mappings.yaml')
    shutil.copy(alias_mapping_resource, path.join(file_server_root,
                                                  'cloudify'
                                                  '/alias-mappings.yaml'))
