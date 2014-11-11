import supervise

DEFAULT_SERVICE_DIR = '/etc/service'
UNKNOWN_SERVICE_EXCEPT_MSG = '[Errno 2] No such file or directory: \'' + \
                             DEFAULT_SERVICE_DIR + '/{0}' +\
                             '/supervise/status' + '\''
supervise.DEFAULT_SERVICE_DIR = DEFAULT_SERVICE_DIR


def is_job(name):
    """Return True if name is registred upstart job"""
    try:
        service = supervise.Service(name)
        service.status()
    except IOError as e:
        if e.__str__() == UNKNOWN_SERVICE_EXCEPT_MSG.format(name):
            return False
        else:
            raise e
    return True


def get_job_details(name):
    """Return job details (properties + instances)."""
    if is_job(name):
        props = dict()
        props.update({'instances': get_instance_properties(name)})
        return props
    else:
        return None


def get_jobs(jobs, names=[]):
    """
    Return list of jobs and their job details.

    Args:
        jobs (list): list of job names to return
        names (list): list of display names for jobs

    """
    output = []
    for job, name in map(None, jobs, names):
        job_details = get_job_details(job)
        display_name = {'display_name': name or job}
        if job_details:
            job_details.update(display_name)
            output.append(job_details)
        else:
            output.append(display_name)
    return output


def get_instance_properties(name, keys=['uptime', 'status', 'pid']):
    """
    Return instance properties.

    Args:
        name (str): job name
        keys (list): list of property names to get
    """
    out = []
    s = supervise.Service(name)
    service_status = s.status()
    props = service_status.__dict__
    for key in props.keys():
        if key not in keys:
            del props[key]
    props.update({'state': service_status._status2str(props['status'])})
    out.append(props)
    return out
