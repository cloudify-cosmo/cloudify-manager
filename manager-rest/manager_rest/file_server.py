__author__ = 'dan'

from multiprocessing import Process
import SimpleHTTPServer
import SocketServer
import os

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
        except BaseException:
            pass

    def start_impl(self):
        import logging
        logging.basicConfig(level=logging.DEBUG)
        logging.info('Starting file server and serving files from: %s', self.root_path)
        os.chdir(self.root_path)

        class TCPServer(SocketServer.TCPServer):
            allow_reuse_address = True
        httpd = TCPServer(('0.0.0.0', PORT), SimpleHTTPServer.SimpleHTTPRequestHandler)
        httpd.serve_forever()
