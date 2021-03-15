#########
# Copyright (c) 2013 GigaSpaces Technologies Ltd. All rights reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
#  * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  * See the License for the specific language governing permissions and
#  * limitations under the License.

import os
import re
import glob
import errno
import shutil
import zipfile
import tempfile
from dateutil import rrule
from base64 import b64encode
from datetime import datetime
from os import path, makedirs
from dateutil import parser as date_parser

from flask import g
from flask import request
from werkzeug.local import LocalProxy
from flask_security import current_user

from dsl_parser.constants import HOST_AGENT_PLUGINS_TO_INSTALL

from cloudify import logs
from cloudify.constants import BROKER_PORT_SSL
from cloudify.models_states import VisibilityState
from cloudify.amqp_client import create_events_publisher, get_client

from manager_rest import constants, config, manager_exceptions
from manager_rest.constants import EQUAL, NOT_EQUAL, IS_NULL, IS_NOT_NULL


def check_allowed_endpoint(allowed_endpoints):
    # Getting the resource from the endpoint, for example 'status' or 'sites'
    # from 'v3.1/status' and 'v3.1/sites/<string:name>'. GET /version url
    # is the only one that excludes the api version
    if request.endpoint is None:
        return False
    endpoint_parts = request.endpoint.split('/')
    request_endpoint = endpoint_parts[1] if len(endpoint_parts) > 1 else \
        endpoint_parts[0]
    request_method = request.method.lower()
    for allowed_endpoint in allowed_endpoints:
        if isinstance(allowed_endpoint, tuple):
            if request_endpoint == allowed_endpoint[0]:
                return request_method == allowed_endpoint[1]
        else:
            if request_endpoint == allowed_endpoint:
                return True

    return False


def is_sanity_mode():
    return os.path.isfile(constants.SANITY_MODE_FILE_PATH)


def is_internal_request():
    remote_addr = _get_remote_addr()
    http_hosts = [_get_host(), constants.LOCAL_ADDRESS]

    # cloudify-rest is the host for the auth request for the file-server
    return remote_addr in http_hosts or 'cloudify-rest' in _get_host()


def _get_host():
    return request.host


def _get_remote_addr():
    return request.remote_addr


def copy_resources(file_server_root, resources_path=None):
    if resources_path is None:
        resources_path = path.abspath(__file__)
        for i in range(3):
            resources_path = path.dirname(resources_path)
        resources_path = path.join(resources_path, 'resources')
    cloudify_resources = path.join(resources_path,
                                   'rest-service',
                                   'cloudify')
    shutil.copytree(cloudify_resources, path.join(file_server_root,
                                                  'cloudify'))


def mkdirs(folder_path):
    try:
        makedirs(folder_path)
    except OSError as exc:
        if exc.errno == errno.EEXIST and path.isdir(folder_path):
            pass
        else:
            raise


def create_filter_params_list_description(parameters, list_type):
    return [{'name': filter_val,
             'description': 'List {type} matching the \'{filter}\' '
                            'filter value'.format(type=list_type,
                                                  filter=filter_val),
             'required': False,
             'allowMultiple': False,
             'dataType': 'string',
             'defaultValue': None,
             'paramType': 'query'} for filter_val in parameters]


def is_bypass_maintenance_mode(request):
    bypass_maintenance_header = 'X-BYPASS-MAINTENANCE'
    return request.headers.get(bypass_maintenance_header)


def get_plugin_archive_path(plugin_id, archive_name):
    return os.path.join(
        config.instance.file_server_root,
        constants.FILE_SERVER_PLUGINS_FOLDER,
        plugin_id,
        archive_name
    )


def get_formatted_timestamp():
    # Adding 'Z' to match ISO format
    return '{0}Z'.format(datetime.utcnow().isoformat()[:-3])


class classproperty(object):  # NOQA  # class CapWords
    """A class that acts a a decorator for class-level properties

    class A(object):
        _prop1 = 1
        _prop2 = 2

        @classproperty
        def foo(cls):
            return cls._prop1 + cls._prop2

    And use it like this:
    print A.foo  # 3

    """
    def __init__(self, get_func):
        self.get_func = get_func

    def __get__(self, _, owner_cls):
        return self.get_func(owner_cls)


def create_auth_header(username=None, password=None, token=None, tenant=None):
    """Create a valid authentication header either from username/password or
    a token if any were provided; return an empty dict otherwise
    """
    headers = {}
    if username and password:
        credentials = b64encode(
            '{0}:{1}'.format(username, password).encode('utf-8')
        ).decode('ascii')
        headers = {
            constants.CLOUDIFY_AUTH_HEADER:
            constants.BASIC_AUTH_PREFIX + credentials
        }
    elif token:
        headers = {constants.CLOUDIFY_AUTH_TOKEN_HEADER: token}
    if tenant:
        headers[constants.CLOUDIFY_TENANT_HEADER] = tenant
    return headers


def all_tenants_authorization():
    return (
        current_user.id == constants.BOOTSTRAP_ADMIN_ID or
        any(r in current_user.system_roles
            for r in config.instance.authorization_permissions['all_tenants'])
    )


def tenant_specific_authorization(tenant, resource_name, action='list'):
    """
    Return true if the user is permitted to perform a certain action in a
    in a given tenant on a given resource (for filtering purpose).
    """
    resource_name = constants.MODELS_TO_PERMISSIONS.get(resource_name,
                                                        resource_name.lower())
    try:
        permission_name = '{0}_{1}'.format(resource_name, action)
        permission_roles = \
            config.instance.authorization_permissions[permission_name]
    except KeyError:
        permission_roles = \
            config.instance.authorization_permissions[resource_name.lower()]
    return current_user.has_role_in(tenant, permission_roles)


def is_administrator(tenant):
    administrators_roles = \
        config.instance.authorization_permissions['administrators']
    return (
        current_user.id == constants.BOOTSTRAP_ADMIN_ID or
        current_user.has_role_in(tenant, administrators_roles)
    )


def is_create_global_permitted(tenant):
    create_global_roles = \
        config.instance.authorization_permissions['create_global_resource']
    return (
        current_user.id == constants.BOOTSTRAP_ADMIN_ID or
        current_user.has_role_in(tenant, create_global_roles)
    )


def can_execute_global_workflow(tenant):
    execute_global_roles = \
        config.instance.authorization_permissions['execute_global_workflow']
    return (
        current_user.id == constants.BOOTSTRAP_ADMIN_ID or
        current_user.has_role_in(tenant, execute_global_roles)
    )


def validate_global_modification(resource):
    # A global resource can't be modify from outside its tenant
    if resource.visibility == VisibilityState.GLOBAL and \
       resource.tenant_name != current_tenant.name:
        raise manager_exceptions.IllegalActionError(
            "Can't modify the global resource `{0}` from outside its "
            "tenant `{1}`".format(resource.id, resource.tenant_name))


@LocalProxy
def current_tenant():
    tenant = getattr(g, 'current_tenant', None)
    if not tenant:
        raise manager_exceptions.TenantNotProvided(
            'Authorization failed: tenant not provided')
    return tenant


def set_current_tenant(tenant):
    g.current_tenant = tenant


def unzip(archive, destination=None, logger=None):
    if not destination:
        destination = tempfile.mkdtemp()
    if logger:
        logger.debug('Extracting zip {0} to {1}...'.
                     format(archive, destination))
    with zipfile.ZipFile(archive, 'r') as zip_file:
        zip_file.extractall(destination)
    return destination


def files_in_folder(folder, name_pattern='*'):
    files = []
    for item in glob.glob(os.path.join(folder, name_pattern)):
        if os.path.isfile(item):
            files.append(os.path.join(folder, item))
    return files


def remove(path):
    if os.path.exists(path):
        if os.path.isfile(path):
            os.remove(path)
        else:
            shutil.rmtree(path)


def send_event(event, message_type):
    logs.populate_base_item(event, 'cloudify_event')
    events_publisher = create_events_publisher(
        amqp_host=config.instance.amqp_host,
        amqp_user=config.instance.amqp_username,
        amqp_pass=config.instance.amqp_password,
        amqp_port=BROKER_PORT_SSL,
        amqp_vhost='/',
        ssl_enabled=True,
        ssl_cert_path=config.instance.amqp_ca_path
    )

    events_publisher.publish_message(event, message_type)
    events_publisher.close()


def is_visibility_wider(first, second):
    states = VisibilityState.STATES
    return states.index(first) > states.index(second)


def validate_deployment_and_site_visibility(deployment, site):
    if is_visibility_wider(deployment.visibility, site.visibility):
        raise manager_exceptions.IllegalActionError(
            "The visibility of deployment `{0}`: `{1}` can't be wider than "
            "the visibility of it's site `{2}`: `{3}`"
            .format(deployment.id, deployment.visibility, site.name,
                    site.visibility)
        )


def extract_host_agent_plugins_from_plan(plan):
    host_agent_plugins_to_install = plan.get(
        HOST_AGENT_PLUGINS_TO_INSTALL, [])

    if not host_agent_plugins_to_install:
        for node in plan.get('nodes', []):
            for plugin in node.get('plugins_to_install', []):
                host_agent_plugins_to_install.append(plugin)
    return host_agent_plugins_to_install


def get_amqp_client():
    return get_client(
        amqp_host=config.instance.amqp_host,
        amqp_user=config.instance.amqp_username,
        amqp_pass=config.instance.amqp_password,
        amqp_port=BROKER_PORT_SSL,
        amqp_vhost='/',
        ssl_enabled=True,
        ssl_cert_path=config.instance.amqp_ca_path,
        connect_timeout=3,
    )


def get_filters_list_from_mapping(filters_mapping):
    """ Returns a filters list based on the filters mapping """
    filters_list = []
    for item in EQUAL, NOT_EQUAL:
        labels = sorted(filters_mapping.get(item, {}).items())
        for label_key, label_value in labels:
            filters_list.append(_get_label_filter_rule(
                item, label_key, label_value))

    for item in IS_NULL, IS_NOT_NULL:
        for label_key in filters_mapping.get(item, []):
            filters_list.append(_get_label_filter_rule(item, label_key))

    return filters_list


def _get_label_filter_rule(mapping_key, label_key, label_values_list=None):
    mapping = {EQUAL: '=', NOT_EQUAL: '!=',
               IS_NULL: ' is null', IS_NOT_NULL: ' is not null'}

    if mapping_key in (EQUAL, NOT_EQUAL):
        label_values_str = (label_values_list[0] if len(label_values_list) == 1
                            else '[' + ','.join(label_values_list) + ']')

        return label_key + mapping[mapping_key] + label_values_str

    else:  # mapping_key in (IS_NULL, IS_NOT_NULL)
        return label_key + mapping[mapping_key]


def parse_frequency(expr):
    match = r"(\d+)\ ?(sec(ond)?|min(ute)?|h(our)?|d(ay)?|w(eek)?|" \
            r"mo(nth)?|y(ear)?)s?$"
    parsed = re.findall(match, expr)
    if not parsed or len(parsed[0]) < 2:
        return None, None
    return int(parsed[0][0]), parsed[0][1]


def get_rrule(rule, since, until):
    """
    Compute an RRULE for the execution scheduler.

    :param rule: A dictionary representing a scheduling rule.
    Rules are of the following possible formats (e.g.):
        {'frequency': '2 weeks', 'count': 5, 'weekdays': ['SU', 'MO', 'TH']}
           = run every 2 weeks, 5 times totally, only on sun. mon. or thu.
        {'count': 1'} = run exactly once, at the `since` time
        {'rrule': 'RRULE:FREQ=DAILY;INTERVAL=3'} = pass RRULE directly
    :param since: A datetime string representing the earliest time to schedule
    :param until: A datetime string representing the latest time to schedule
    :return: an iCalendar RRULE object
    """
    since = _get_timestamp(since)
    until = _get_timestamp(until)

    if rule.get('rrule'):
        parsed_rule = rrule.rrulestr(rule['rrule'], dtstart=since, cache=True)
        if not parsed_rule._until:
            parsed_rule._until = until
        return parsed_rule

    if not rule.get('frequency'):
        if rule.get('count') == 1:
            frequency = rrule.DAILY
            interval = 0
        else:
            return
    else:
        interval, frequency = parse_frequency(rule['frequency'])
        if not frequency:
            return
        freqs = {'sec': rrule.SECONDLY, 'second': rrule.SECONDLY,
                 'min': rrule.MINUTELY, 'minute': rrule.MINUTELY,
                 'h': rrule.HOURLY, 'hour': rrule.HOURLY,
                 'd': rrule.DAILY, 'day': rrule.DAILY,
                 'w': rrule.WEEKLY, 'week': rrule.WEEKLY,
                 'mo': rrule.MONTHLY, 'month': rrule.MONTHLY,
                 'y': rrule.YEARLY, 'year': rrule.YEARLY}
        frequency = freqs[frequency]

    weekdays = None
    if rule.get('weekdays'):
        weekdays = _get_weekdays(rule['weekdays'])

    if not weekdays:
        return rrule.rrule(freq=frequency, interval=interval,
                           dtstart=since, until=until, count=rule.get('count'),
                           cache=True)

    count = rule.get('count')
    rule_set = _get_rule_set_by_weekdays(
        frequency, interval, since, until, weekdays)
    return _cap_rule_set_by_occurrence_count(rule_set, count)


def _get_rule_set_by_weekdays(frequency, interval, since, until, weekdays):
    rule_set = rrule.rruleset()
    for weekday in weekdays:
        rule_set.rrule(
            rrule.rrule(freq=frequency, interval=interval, dtstart=since,
                        until=until, byweekday=weekday[0], bysetpos=weekday[1],
                        cache=True))
    return rule_set


def _cap_rule_set_by_occurrence_count(rule_set, count):
    if not count:
        return rule_set
    try:
        until_cap = rule_set[count-1]
    except IndexError:
        return rule_set
    capped_rule_set = rrule.rruleset()
    for rule in rule_set._rrule:
        capped_rule_set.rrule(rule.replace(until=until_cap))
    return capped_rule_set


def _get_weekdays(raw_weekdays):
    """
    :param raw_weekdays: a list of strings representing a weekday in 2-letter
        format, e.g. 'MO', 'TU', with an optional prefix representing the
        weekday's position in a month, e.g. '1SU' = first sunday, or
        'L-FR' = last friday
    :return: a corresponding list of tuples, each of the structure:
        (dateutil weekday object, int representing the position in month)
        position = -1 means "last <weekday> of a month"
        position = None means "every <weekday>"
    """
    weekdays_map = {str(wd): wd for wd in rrule.weekdays}
    weekdays = []
    for prefixed_weekday in raw_weekdays:
        weekday, position = prefixed_weekday[-2:], prefixed_weekday[:-2]
        if not position:
            position = None
        elif position == 'L-':
            position = -1
        else:
            position = int(position)
        if weekday in weekdays_map:
            weekdays.append((weekdays_map[weekday], position))
    return weekdays


def _get_timestamp(value):
    if isinstance(value, str):
        return date_parser.parse(value, ignoretz=True)
    else:
        return value
