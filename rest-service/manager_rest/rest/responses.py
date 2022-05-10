from flask_restful import fields
from flask_restful_swagger import swagger


@swagger.model
class BlueprintValidationStatus(object):

    resource_fields = {
        'blueprintId': fields.String(attribute='blueprint_id'),
        'status': fields.String
    }

    def __init__(self, **kwargs):
        self.blueprint_id = kwargs.get('blueprint_id')
        self.status = kwargs.get('status')


@swagger.model
class Workflow(object):

    resource_fields = {
        'name': fields.String,
        'plugin': fields.String,
        'operation': fields.String,
        'parameters': fields.Raw,
        'is_cascading': fields.Boolean,
        'is_available': fields.Boolean,
    }

    def __init__(self, **kwargs):
        self.name = kwargs.get('name')
        self.parameters = kwargs.get('parameters')
        self.plugin = kwargs.get('plugin')
        self.operation = kwargs.get('operation')
        self.is_cascading = kwargs.get('is_cascading', False)
        self.is_available = kwargs.get('is_available', True)

    def as_dict(self):
        return {
            'name': self.name,
            'parameters': self.parameters,
            'plugin': self.plugin,
            'operation': self.operation,
            'is_cascading': self.is_cascading,
            'is_available': self.is_available,
        }

    def __hash__(self):
        return hash(self.name)

    def __eq__(self, other):
        # could also consider params but currently it just merges by name
        return self.name == other.name


@swagger.model
class DeploymentOutputs(object):

    resource_fields = {
        'deployment_id': fields.String,
        'outputs': fields.Raw
    }

    def __init__(self, **kwargs):
        self.deployment_id = kwargs.get('deployment_id')
        self.outputs = kwargs.get('outputs')


@swagger.model
class Status(object):

    resource_fields = {
        'status': fields.String,
        'services': fields.Raw
    }

    def __init__(self, **kwargs):
        self.status = kwargs.get('status')
        self.services = kwargs.get('services')


@swagger.model
class ProviderContextPostStatus(object):

    resource_fields = {
        'status': fields.String
    }

    def __init__(self, **kwargs):
        self.status = kwargs.get('status')


@swagger.model
class Version(object):

    resource_fields = {
        'edition': fields.String,
        'version': fields.String,
        'build': fields.String,
        'date': fields.String,
        'commit': fields.String,
        'distribution': fields.String,
        'distro_release': fields.String,
    }

    def __init__(self, **kwargs):
        self.edition = kwargs.get('edition')
        self.version = kwargs.get('version')
        self.build = kwargs.get('build')
        self.date = kwargs.get('date')
        self.commit = kwargs.get('commit')
        self.distribution = kwargs.get('distribution')
        self.distro_release = kwargs.get('distro_release')


@swagger.model
class EvaluatedFunctions(object):

    resource_fields = {
        'deployment_id': fields.String,
        'payload': fields.Raw
    }

    def __init__(self, **kwargs):
        self.deployment_id = kwargs.get('deployment_id')
        self.payload = kwargs.get('payload')


@swagger.model
class Tokens(object):

    resource_fields = {
        'id': fields.String,
        'username': fields.String,
        'value': fields.String,
        'role': fields.String,
        'expiration_date': fields.String,
        'last_used': fields.String,
        'description': fields.String,
    }

    def __init__(self, **kwargs):
        self.id = kwargs.get('id')
        self.username = kwargs.get('username')
        self.value = kwargs.get('value')
        self.role = kwargs.get('role')
        self.expiration_date = kwargs.get('expiration_date')
        self.last_used = kwargs.get('last_used')
        self.description = kwargs.get('description')


@swagger.model
class Label(object):

    resource_fields = {
        'key': fields.String,
        'value': fields.String,
        'created_at': fields.String,
        'creator_id': fields.Integer
    }

    def __init__(self, **kwargs):
        self.key = kwargs.get('key')
        self.value = kwargs.get('value')
        self.created_at = kwargs.get('created_at')
        self.creator_id = kwargs.get('creator_id')
