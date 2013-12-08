__author__ = 'dan'


class Config(object):

    def __init__(self):
        self._file_server_root = None
        self._workflow_service_base_uri = None
        self._events_files_path = None
        self._test_mode = False

    @property
    def file_server_root(self):
        return self._file_server_root

    @file_server_root.setter
    def file_server_root(self, value):
        self._file_server_root = value

    @property
    def workflow_service_base_uri(self):
        return self._workflow_service_base_uri

    @workflow_service_base_uri.setter
    def workflow_service_base_uri(self, value):
        self._workflow_service_base_uri = value

    @property
    def events_files_path(self):
        return self._events_files_path

    @events_files_path.setter
    def events_files_path(self, value):
        self._events_files_path = value

    @property
    def test_mode(self):
        return self._test_mode

    @test_mode.setter
    def test_mode(self, value):
        self._test_mode = value


_instance = Config()


def reset(configuration=None):
    global _instance
    if configuration is not None:
        _instance = configuration
    else:
        _instance = Config()


def instance():
    return _instance