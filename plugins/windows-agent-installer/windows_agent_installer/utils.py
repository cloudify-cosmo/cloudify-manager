import winrm

__author__ = 'elip'

DEFAULT_WINRM_PORT = '5985'
DEFAULT_WINRM_URI = 'wsman'
DEFAULT_WINRM_PROTOCOL = 'http'


class WinRMRunner(object):

    def __init__(self, ctx, worker_config=None):
        self.ctx = ctx
        self.worker_config = worker_config
        self.session = self._create_session()

    def _create_session(self):

        winrm_url = '{0}://{1}:{2}/{3}'.format(
            self.worker_config['protocol'],
            self.worker_config['host'],
            self.worker_config['port'],
            self.worker_config['uri'])
        return winrm.Session(winrm_url, auth=(self.worker_config['user'],
                                              self.worker_config['password']))

    def run(self, command, exit_on_failure=True):

        def _chk(res):
            r = res
            if r.status_code == 0:
                self.ctx.logger.debug('Command executed successfully')
                if not len(r.std_out) == 0:
                    self.ctx.logger.debug(r.std_out)
            else:
                self.ctx.logger.debug('Command execution failed while executing: {0}, with code: {1}'
                    .format(command, r.status_code))
                if not len(r.std_err) == 0:
                    self.ctx.logger.error(r.std_err)
                else:
                    self.ctx.logger.error('Unknown error')
                if exit_on_failure:
                    raise RuntimeError

        self.ctx.logger.debug('Executing: {0}'.format(command))
        response = self.session.run_cmd(command)
        _chk(response)
        return response

    def download(self, url, output_path):
        self.ctx.logger.debug('Downloading {0}...'.format(url))
        return self.run(
            '''@powershell -Command "(new-object System.Net.WebClient).Downloadfile('{0}','{1}')"'''  # NOQA
            .format(url, output_path))
