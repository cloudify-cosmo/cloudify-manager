import dbus

BUS_NAME = 'com.ubuntu.Upstart'
BASE_PATH = '/com/ubuntu/Upstart'
UPSTART_IFACE = 'com.ubuntu.Upstart0_6'
UPSTARTJOB_IFACE = 'com.ubuntu.Upstart0_6.Job'
UPSTARTINST_IFACE = 'com.ubuntu.Upstart0_6.Instance'
UNKNOWNJOB_EXCEPT = 'com.ubuntu.Upstart0_6.Error.UnknownJob'

_sysbus = dbus.SystemBus()
_upstart_proxy = _sysbus.get_object(BUS_NAME, BASE_PATH)


def is_job(name):
    """Return True if name is registred upstart job"""
    try:
        _upstart_proxy.GetJobByName(name, dbus_interface=UPSTART_IFACE)
    except dbus.exceptions.DBusException as e:
        if e.get_dbus_name() == UNKNOWNJOB_EXCEPT:
            return False
        else:
            raise e
    return True


def has_instances(name):
    job = _get_job_proxy(name)
    if job:
        instances = job.GetAllInstances(dbus_interface=UPSTARTJOB_IFACE)
        return True if instances else False
    else:
        return False


def get_jobs(jobs, names=[]):
    """
    Return dict of jobs and their job details.

    Args:
        jobs (list): list of job names to return
        names (list): alternative names for jobs

    """
    return {name or job: get_job_details(job)
            for job, name in map(None, jobs, names)}


def get_job_details(name):
    """Return job details (properties + instances)."""
    if is_job(name):
        props = get_job_properties(name)
        props.update({'instances': get_instance_properties(name)})
        return props
    else:
        return None


def get_job_properties(name, keys=['name', 'description']):
    """
    Return job details.

    Args:
        name (str): job name
        keys (list): list of property names to get
    """
    job = _get_job_proxy(name)
    if job:
        props = job.GetAll(UPSTARTJOB_IFACE,
                           dbus_interface=dbus.PROPERTIES_IFACE)
        for key in props.keys():
            if key not in keys:
                del props[key]
        return props
    else:
        return None


def get_instance_properties(name, keys=['processes', 'state', 'name']):
    """
    Return instance properties.

    Args:
        name (str): job name
        keys (list): list of property names to get
    """
    out = []
    for path in _get_instances_path(name) or []:
        instance = _sysbus.get_object(BUS_NAME, path)
        props = instance.GetAll(UPSTARTINST_IFACE,
                                dbus_interface=dbus.PROPERTIES_IFACE)
        for key in props.keys():
            if key not in keys:
                del props[key]
        out.append(props)
    return out


def _get_job_proxy(name):
    if is_job(name):
        path = _upstart_proxy.GetJobByName(name, dbus_interface=UPSTART_IFACE)
        return _sysbus.get_object(BUS_NAME, path)
    else:
        return None


def _get_instances_path(name):
    job = _get_job_proxy(name)
    if job:
        return job.GetAllInstances(dbus_interface=UPSTARTJOB_IFACE)
    else:
        return None
