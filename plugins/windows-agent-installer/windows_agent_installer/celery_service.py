"""
The most basic (working) Windows service possible.
Requires Mark Hammond's pywin32 package.
Most of the code was taken from a CherryPy 2.2 example of how to set up a
service
"""
# import pkg_resources
import os
import sys
import ConfigParser

from paste.script.serve import ServeCommand as Server
import win32serviceutil
import win32service
import win32event


SCRIPT_DIR = os.path.abspath(os.path.dirname(__file__))
INI_FILE = 'celeryd.ini'
SERV_SECTION = 'celery:service'
SERV_NAME = 'service_name'
SERV_DISPLAY_NAME = 'service_display_name'
SERV_DESC = 'service_description'
SERV_LOG_FILE = 'service_logfile'
SERV_APPLICATION = 'celeryd'
SERV_LOG_FILE_VAR = 'CELERYD_LOG_FILE'

# Default Values
SERV_NAME_DEFAULT = 'CloudifyAgent'
SERV_DISPLAY_NAME_DEFAULT = 'Cloudify Agent'
SERV_DESC_DEFAULT = 'WSCGI Windows Celery Service'
SERV_LOG_FILE_DEFAULT = r'c:\cloudify\celery.log'


class DefaultSettings(object):
    def __init__(self):
        if SCRIPT_DIR:
            os.chdir(SCRIPT_DIR)
        # find the ini file
        self.ini = os.path.join(SCRIPT_DIR, INI_FILE)
        # create a config parser opject and populate it with the ini file
        c = ConfigParser.SafeConfigParser()
        c.read(self.ini)
        self.c = c

    def get_defaults(self):
        """
        Check for and get the default settings
        """
        if (
            (not self.c.has_section(SERV_SECTION)) or
            (not self.c.has_option(SERV_SECTION, SERV_NAME)) or
            (not self.c.has_option(SERV_SECTION, SERV_DISPLAY_NAME)) or
            (not self.c.has_option(SERV_SECTION, SERV_DESC)) or
            (not self.c.has_option(SERV_SECTION, SERV_LOG_FILE))
        ):
            print 'setting defaults'
            self.set_defaults()
        service_name = self.c.get(SERV_SECTION, SERV_NAME)
        service_display_name = self.c.get(SERV_SECTION, SERV_DISPLAY_NAME)
        service_description = self.c.get(SERV_SECTION, SERV_DESC)
        iniFile = self.ini
        service_logfile = self.c.get(SERV_SECTION, SERV_LOG_FILE)
        return (service_name, service_display_name, service_description,
                iniFile, service_logfile)

    def set_defaults(self):
        """
        set and add the default setting to the ini file
        """
        if not self.c.has_section(SERV_SECTION):
            self.c.add_section(SERV_SECTION)
        self.c.set(SERV_SECTION, SERV_NAME, SERV_NAME_DEFAULT)
        self.c.set(SERV_SECTION, SERV_DISPLAY_NAME, SERV_DISPLAY_NAME_DEFAULT)
        self.c.set(SERV_SECTION, SERV_DESC, SERV_DESC_DEFAULT)
        self.c.set(SERV_SECTION, SERV_LOG_FILE, SERV_LOG_FILE_DEFAULT)
        with open('self.ini', 'w+') as f:
            self.c.write(f)
        msg = ('you must set the celery:service section service_name,'
               ' service_display_name, and service_description options to'
               ' define the service in the {} file'.format(self.ini))
        sys.exit(msg)


class CeleryService(win32serviceutil.ServiceFramework):
    """NT Service."""

    d = DefaultSettings()
    (service_name, service_display_name, service_description,
     iniFile, logFile) = d.get_defaults()

    _svc_name_ = service_name
    _svc_display_name_ = service_display_name
    _svc_description_ = service_description

    def __init__(self, args):
        win32serviceutil.ServiceFramework.__init__(self, args)
        # create an event that SvcDoRun can wait on and SvcStop
        # can set.
        self.stop_event = win32event.CreateEvent(None, 0, 0, None)

    def SvcDoRun(self):
        os.chdir(SCRIPT_DIR)
        s = Server(SERV_APPLICATION)
        os.environ[SERV_LOG_FILE_VAR] = self.logFile
        s.run([self.iniFile])
        win32event.WaitForSingleObject(self.stop_event, win32event.INFINITE)

    def SvcStop(self):
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        # win32event.SetEvent(self.stop_event)
        self.ReportServiceStatus(win32service.SERVICE_STOPPED)
        sys.exit()

if __name__ == '__main__':
    win32serviceutil.HandleCommandLine(CeleryService)
