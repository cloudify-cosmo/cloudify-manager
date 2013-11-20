__author__ = 'dan'

from multiprocessing import Process
import SimpleHTTPServer
import SocketServer
import os
import signal
import time

PORT = 53229


class FileServer(object):

    def __init__(self, root_path):
        self.root_path = root_path
        self.process = Process(target=self.start_impl)

    def start(self):
        self.process.start()

    def stop(self):
        self.process.terminate()

    def start_impl(self):
        print 'Starting file server and serving files from: ', self.root_path
        os.chdir(self.root_path)
        Handler = SimpleHTTPServer.SimpleHTTPRequestHandler
        class TCPServer(SocketServer.TCPServer):
            allow_reuse_address = True
        httpd = TCPServer(('0.0.0.0', PORT), Handler)
        # def handle(signum, frame):
        #     print 'Shutting down file server'
        #     httpd.shutdown()
        #     time.sleep(1)
        #     httpd.server_close()
        # for sig in [signal.SIGTERM, signal.SIGINT, signal.SIGQUIT]:
        #     signal.signal(sig, handle)
        httpd.serve_forever()
