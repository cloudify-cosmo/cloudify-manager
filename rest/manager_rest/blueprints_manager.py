__author__ = 'dan'

from dsl_parser import tasks
import json
from responses import BlueprintState


class BlueprintsManager(object):

    def __init__(self):
        self.blueprints = {}

    def blueprints_list(self):
        return self.blueprints.values()

    # TODO: call celery tasks instead of doing this directly here
    def publish(self, dsl_location, alias_mapping_url, resources_base_url):
        plan = tasks.parse_dsl(dsl_location, alias_mapping_url, resources_base_url)
        plan = tasks.prepare_multi_instance_plan(json.loads(plan))
        new_blueprint = BlueprintState(json_plan=plan, plan=json.loads(plan))
        self.blueprints[new_blueprint.id] = new_blueprint
        return new_blueprint
