__author__ = 'dan'

from multiprocessing import Process
import SimpleHTTPServer
import SocketServer


class FileServer(object):

    def __init__(self):
        self.process = Process(target=self.start_impl)

    def start(self):
        self.process.start()

    def stop(self):
        self.process.terminate()

    def start_impl(self):
        Handler = SimpleHTTPServer.SimpleHTTPRequestHandler
        httpd = SocketServer.TCPServer(("", 53229), Handler)
        httpd.serve_forever()

