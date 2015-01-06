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

from cloudify.tests import get_logger

PORT = 53229
FNULL = open(os.devnull, 'w')


logger = get_logger('FileServer')


class FileServer(object):

    def __init__(self, root_path, use_subprocess=False, timeout=5):
        self.root_path = root_path
        self.process = Process(target=self.start_impl)
        self.use_subprocess = use_subprocess
        self.timeout = timeout

    def start(self):
        logger.info("Starting file server")
        if self.use_subprocess:
            subprocess.Popen(
                [sys.executable, __file__, self.root_path],
                stdin=FNULL,
                stdout=FNULL,
                stderr=FNULL)
        else:
            self.process.start()

        end_time = time.time() + self.timeout

        while end_time > time.time():
            if self.is_alive():
                logger.info("File server is up and serving from {0}"
                            .format(self.root_path))
                return
            logger.info("File server is not responding. waiting 10ms")
            time.sleep(0.1)
        raise TimeoutException("Failed starting file server in {0} seconds"
                               .format(self.timeout))

    def stop(self):
        try:
            logger.info("Shutting down file server")
            self.process.terminate()
            while self.is_alive():
                logger.info("File server is still up. waiting for 10ms")
                time.sleep(0.1)
            logger.info("File server has shut down")
        except BaseException:
            pass

    def start_impl(self):
        logger.info('Starting file server and serving files from: %s',
                    self.root_path)
        os.chdir(self.root_path)

        class TCPServer(SocketServer.TCPServer):
            allow_reuse_address = True
        httpd = TCPServer(('0.0.0.0', PORT),
                          SimpleHTTPServer.SimpleHTTPRequestHandler)
        httpd.serve_forever()

    def is_alive(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            s.connect(('localhost', PORT))
            s.close()
            return True
        except socket.error:
            return False


class TimeoutException(Exception):
    def __init__(self, *args):
        Exception.__init__(self, args)

if __name__ == '__main__':
    FileServer(sys.argv[1]).start_impl()
