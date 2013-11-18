__author__ = 'dan'

from dsl_parser import tasks
from responses import BlueprintState


class BlueprintsManager(object):

    def __init__(self):
        self.blueprints = []

    def publish(self, dsl_location, alias_mapping_url, resources_base_url):
        plan = tasks.parse_dsl_impl(dsl_location, alias_mapping_url, resources_base_url)
        plan = tasks.prepare_multi_instance_plan_impl(plan)
        self.blueprints.append(BlueprintState(yml=plan))

