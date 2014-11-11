import supervise

DEFAULT_SERVICE_DIR = '/etc/service'
UNKNOWN_SERVICE_EXCEPT_MSG = '[Errno 2] No such file or directory: \'' + \
                             DEFAULT_SERVICE_DIR + '/{0}' +\
                             '/supervise/status' + '\''
supervise.DEFAULT_SERVICE_DIR = DEFAULT_SERVICE_DIR


def is_service(name):
    """
    Check if service exists.
    :param name: The service name.
    :return: True if service exists. False if otherwise.
    """
    try:
        service = supervise.Service(name)
        service.status()
    except IOError as e:
        if e.__str__() == UNKNOWN_SERVICE_EXCEPT_MSG.format(name):
            return False
        else:
            raise e
    return True


def get_service_details(name):
    """
    Returns service deployment details
    :param name: The service name
    :return: Service details.
    """
    if is_service(name):
        props = dict()
        props.update({'instances': get_instance_properties(name)})
        return props
    else:
        return None


def get_services(services, names=()):
    """
    Returns service deployment details for all requested jobs.
    :param services: Service names
    :param name: Service screen name.
    :return: Service details.
    """
    output = []
    for service, name in map(None, services, names):
        service_details = get_service_details(service)
        display_name = {'display_name': name or service}
        if service_details:
            service_details.update(display_name)
            output.append(service_details)
        else:
            output.append(display_name)
    return output


def get_instance_properties(name):
    """
    Returns service instance deployment properties.
    :param name: Service screen name.
    :return: Instance properties.
    """
    out = []
    s = supervise.Service(name)
    service_status = s.status()
    props = {
        'uptime': service_status.uptime,
        'pid': service_status.pid,
        'state': service_status._status2str(service_status.status)
    }
    out.append(props)
    return out
