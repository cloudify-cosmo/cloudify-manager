#########
# Copyright (c) 2013 GigaSpaces Technologies Ltd. All rights reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
#  * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  * See the License for the specific language governing permissions and
#  * limitations under the License.

from multiprocessing import Process
import subprocess
import SimpleHTTPServer
import SocketServer
import os
import sys
import socket
import time

PORT = 53229
FNULL = open(os.devnull, 'w')


class FileServer(object):

    def __init__(self, root_path, use_subprocess=False, port=PORT):
        self.root_path = root_path
        self.process = Process(target=self.start_impl)
        self.use_subprocess = use_subprocess
        self.port = port

    def validate_port_free(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        result = sock.connect_ex(('localhost', self.port))
        if result == 0:
            raise Exception('FileServer port is already taken ({0})'
                            .format(self.port))

    def start(self):
        self.validate_port_free()
        if self.use_subprocess:
            subprocess.Popen(
                [sys.executable, __file__, self.root_path],
                stdin=FNULL,
                stdout=FNULL,
                stderr=FNULL)
        else:
            self.process.start()
            while not self.is_alive():
                time.sleep(0.1)

    def stop(self):
        import logging
        logging.basicConfig(level=logging.INFO)
        if not self.process.is_alive():
            return
        try:
            pid = self.process.pid
            self.process.terminate()
            self.process.join()
        except BaseException as e:
            exc_type, exc, traceback = sys.exc_info()
            logging.info('Failed to stop file_server, error: {0}'
                         .format(e)), None, traceback
        else:
            if pid:
                logging.info('stopped file server process: {0}'.format(pid))
            else:
                logging.info('stopped file server process, pid unknown')

    def start_impl(self):
        os.chdir(self.root_path)

        class TCPServer(SocketServer.TCPServer):
            allow_reuse_address = True
        httpd = TCPServer(('0.0.0.0', self.port),
                          SimpleHTTPServer.SimpleHTTPRequestHandler)
        httpd.serve_forever()

    def is_alive(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            s.connect(('localhost', self.port))
            s.close()
            return True
        except socket.error:
            return False


if __name__ == '__main__':
    FileServer(sys.argv[1]).start_impl()
