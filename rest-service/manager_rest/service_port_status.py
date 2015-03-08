import socket


def _is_port_occupied(port):
    try:
        s = socket.create_connection(('localhost', port))
        s.close()
        return True
    except socket.error as err:
        print(err)
        pass


def _are_ports_occupied(ports):
    occupied = True
    for port in ports:
        if not _is_port_occupied(port):
            occupied = False
    return occupied


def get_service_state(ports):
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
    output = []
    for service_name, ports in services.items():
        service_details = {'state': get_service_state(ports),
                           'display_name': service_name}
        output.append(service_details)
    return output


def _get_service_port_dict():
    job_list = {'Riemann': [],
                'RabbitMQ': [5672],
                'Celery Management': [],
                'Elasticsearch': [9200],
                'Cloudify UI': [9001],
                'Logstash': [9999],
                'Webserver': [80, 53229],
                'InfluxDB': [8083, 8086],
                'Manager rest-service': [8100]
                }
    return job_list
