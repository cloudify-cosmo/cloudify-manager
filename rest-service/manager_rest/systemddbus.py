import dbus

SYSTEMD_BUS = 'org.freedesktop.systemd1'
SYSTEMD_PATH = '/org/freedesktop/systemd1'
MANAGER_IFACE = 'org.freedesktop.systemd1.Manager'
PROP_IFACE = 'org.freedesktop.DBus.Properties'
UNIT_IFACE = 'org.freedesktop.systemd1.Unit'
SVC_IFACE = 'org.freedesktop.systemd1.Service'


class DBusClient:
    SVC_PROPERTIES = ['MainPID']
    UNIT_PROPERTIES = ['Id', 'Description', 'LoadState', 'ActiveState',
                       'SubState']

    def __init__(self):
        self.bus = dbus.SystemBus()
        self.proxy = self.bus.get_object(SYSTEMD_BUS, SYSTEMD_PATH)
        self.interface = dbus.Interface(self.proxy, MANAGER_IFACE)

    def get_properties(self, name, prop_names, property_interface):
        objpath = self.interface.GetUnit(name)
        proxy = self.bus.get_object(SYSTEMD_BUS, objpath)
        interface = dbus.Interface(proxy, PROP_IFACE)
        properties = interface.GetAll(property_interface)
        if prop_names:
            tmp_properties = {}
            for item in prop_names:
                if item in properties:
                    tmp_properties[item] = properties[item]
                else:
                    tmp_properties[item] = None
            properties = tmp_properties
        return properties

    def get_unit_properties(self, unit_name, property_names=UNIT_PROPERTIES):
        return self.get_properties(unit_name, property_names, UNIT_IFACE)

    def get_service_properties(self, unit_name, property_names=SVC_PROPERTIES):
        return self.get_properties(unit_name, property_names, SVC_IFACE)


def get_services(units):
    out = []
    client = DBusClient()
    for unit_id, display_name in units.iteritems():
        service = {}
        service['display_name'] = display_name
        service['instances'] = []
        try:
            instance = {}
            instance.update(client.get_unit_properties(unit_id))
            instance.update(client.get_service_properties(unit_id))
            instance['state'] = instance['SubState']
            service['instances'].append(instance)
        except dbus.exceptions.DBusException:
            pass
        out.append(service)
    return out
