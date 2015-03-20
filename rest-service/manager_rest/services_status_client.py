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
            return {'state': 'up'}
    except IOError:
        pass
    return {'state': 'down'}


def _get_service_state_by_port(ports):
    if _are_ports_occupied(ports):
        return {'state': 'up'}
    return {'state': 'down'}


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
            out.append(_get_elasticsearch_status())
        else:
            out.append(_get_service_state_by_port(ports))
        instances = {'instances': out}
        instances.update({'display_name': service_name})
        result.append(instances)
    return result
