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

__author__ = 'dan'

from multiprocessing import Process
import SimpleHTTPServer
import SocketServer
import os
import socket
import time

PORT = 53229


class FileServer(object):

    def __init__(self, root_path):
        self.root_path = root_path
        self.process = Process(target=self.start_impl)

    def start(self):
        self.process.start()

    def stop(self):
        try:
            self.process.terminate()
            while self.is_alive():
                time.sleep(0.1)
        except BaseException:
            pass

    def start_impl(self):
        import logging
        logging.basicConfig(level=logging.DEBUG)
        logging.info('Starting file server and serving files from: %s',
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
