__author__ = 'dan'

from dsl_parser import tasks
import json
from responses import BlueprintState


class BlueprintsManager(object):

    def __init__(self):
        self._blueprints = []

    @property
    def blueprints(self):
        return self._blueprints

    # TODO: call celery tasks instead of doing this directly here
    def publish(self, dsl_location, alias_mapping_url, resources_base_url):
        json_plan = tasks.parse_dsl(dsl_location, alias_mapping_url, resources_base_url)
        plan = json.loads(json_plan)
        new_json_plan = tasks.prepare_multi_instance_plan(plan)
        new_plan = json.loads(new_json_plan)
        new_blueprint = BlueprintState(json_plan=new_json_plan, plan=new_plan)
        self.blueprints.append(new_blueprint)
        return new_blueprint
