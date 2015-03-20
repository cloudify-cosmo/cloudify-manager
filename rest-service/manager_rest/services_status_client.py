import socket
import urllib
import json


def _is_port_occupied(port):
    try:
        s = socket.create_connection(('hostingvm', int(port)))
        s.close()
        return True
    except socket.error:
        pass


def _are_ports_occupied(ports):
    occupied = True
    for port in ports:
        if not _is_port_occupied(port):
            occupied = False
    return occupied


def _get_elasticsearch_status():
    try:
        response = urllib.urlopen(
            'http://hostingvm:9200/_cluster/health?pretty=false')
        res_body = json.loads(response.readlines()[0])
        service_status = res_body['status']
        status = response.getcode()
        if status == 200 and service_status == 'yellow':
            return 'up'
    except IOError:
        pass
    return 'down'


def _get_service_state_by_port(ports):
    if _are_ports_occupied(ports):
        return 'up'
    return 'down'


def get_services_status(services):
    """
    Returns services status according to its' port status.
    :param services: a dict having service names as keys and ports list as
                     values.
    :return: a dictionary containing status for all services.
    """
    result = []
    for service_name, ports in services.items():
        out = []
        if service_name == 'Elasticsearch':
            service_state = _get_elasticsearch_status()
        else:
            service_state = _get_service_state_by_port(ports)
        out.append({'state': service_state,
                    'display_name': service_name})
        instances = {'instances': out}
        result.append(instances)
    return result
