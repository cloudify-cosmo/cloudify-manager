#/*******************************************************************************
# * Copyright (c) 2013 GigaSpaces Technologies Ltd. All rights reserved
# *
# * Licensed under the Apache License, Version 2.0 (the "License");
# * you may not use this file except in compliance with the License.
# * You may obtain a copy of the License at
# *
# *       http://www.apache.org/licenses/LICENSE-2.0
# *
# * Unless required by applicable law or agreed to in writing, software
# * distributed under the License is distributed on an "AS IS" BASIS,
#    * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    * See the License for the specific language governing permissions and
#    * limitations under the License.
# *******************************************************************************/

import argparse
import threading
import bernhard
import time
import sys
import signal
import os
import logging
from fabric import api


class VagrantStatusMonitor(object):

    def __init__(self, args):
        print args
        self.ssh_user = args.ssh_user
        self.ssh_keyfile = args.ssh_keyfile
        self.ssh_host = args.ssh_host
        self.ssh_port = args.ssh_port
        self.timer = None
        self.interval = args.monitor_interval
        self.vagrant_nic = args.vagrant_nic
        self.tags = [args.tag] if args.tag else []
        self.client = self.create_riemann_client(args.riemann_host,
                                                 args.riemann_port,
                                                 args.riemann_transport)
        self.register_signal_handlers()
        self.monitor()

    def monitor(self):
        self.probe_and_publish()
        self.timer = threading.Timer(self.interval, self.monitor)
        self.timer.start()

    def probe_and_publish(self):
        try:
            host = self.extract_nic_address()
            if len(host) == 0:
                return
            event = {
                'host': host,
                'service': 'vagrant machine status',
                'time': int(time.time()),
                'state': 'running',
                'tags': self.tags,
                'ttl': self.interval * 3
            }
            self.client.send(event)
        except Exception, e:
            sys.stderr.write("Vagrant monitor error: {0}\n".format(e))

    def extract_nic_address(self):
        try:
            with api.settings(host_string=self.ssh_host,
                              port=self.ssh_port,
                              user=self.ssh_user,
                              key_filename=self.ssh_keyfile,
                              disabled_known_hosts=True,
                              abort_on_prompts=True,
                              remote_interrupt=False):
                with api.hide('aborts', 'running', 'stdout', 'stderr'):
                    # TODO: test this.
                    # extract ip from ifconfig output
                    return api.run("ifconfig {0} | \
                                    grep 'inet addr:' | \
                                    cut -d: -f2 | \
                                    cut -d' ' -f1".format(self.vagrant_nic))
        # fabric does sys.exit when it aborts a connection
        except SystemExit:
            return ''
        except Exception:
            return ''

    def create_riemann_client(self, host, port, transport):
        if transport == 'tcp':
            transport_cls = bernhard.TCPTransport
        else:
            transport_cls = bernhard.UDPTransport
        return bernhard.Client(host, port, transport_cls)

    def register_signal_handlers(self):
        def handle(signum, frame):
            self.close()
        signal.signal(signal.SIGTERM, handle)
        signal.signal(signal.SIGINT, handle)
        signal.signal(signal.SIGQUIT, handle)

    def close(self):
        self.client.disconnect()
        if self.timer:
            self.timer.cancel()


def parse_arguments():
    parser = argparse.ArgumentParser(
        description= 'Monitors a given Vagrantfile status and sends it to a riemann server'
    )
    parser.add_argument(
        '--tag',
        help        = 'The tag to attach to riemann events'
    )
    parser.add_argument(
        '--riemann_host',
        help        = 'The riemann host',
        default     = 'localhost'
    )
    parser.add_argument(
        '--riemann_port',
        help        = 'The riemann port',
        default     = 5555,
        type        = int
    )
    parser.add_argument(
        '--riemann_transport',
        help        = 'The riemann transport',
        default     = 'tcp',
        choices     = ['tcp', 'udp']
    )
    parser.add_argument(
        '--ssh_host',
        help        = 'The ssh host as appears in vagrant',
        default     = '127.0.0.1'
    )
    parser.add_argument(
        '--ssh_port',
        help        = 'The ssh port as appears in vagrant',
        default     = 2222,
        type        = int
    )
    parser.add_argument(
        '--ssh_user',
        help        = 'The vagrant guest machine username to connect with',
        default     = 'vagrant'
    )
    parser.add_argument(
        '--ssh_keyfile',
        help        = 'The ssh keyfile used to connect',
        default     = '~/.vagrant.d/insecure_private_key'
    )
    parser.add_argument(
        '--monitor_interval',
        help        = 'The interval in seconds to wait between each probe',
        default     = 5,
        type        = int
    )
    parser.add_argument(
        '--vagrant_nic',
        help        = 'The nic whose ip address should be included in the riemann events',
        default     = 'eth1'
    )
    parser.add_argument(
        '--pid_file',
        help        = 'Path to a filename that should contain the monitor process id'
    )
    return parser.parse_args()


def write_pid_file(pid_file):
    with open(pid_file, 'w') as f:
        f.write(str(os.getpid()))


def main():
    logging.basicConfig()
    args = parse_arguments()
    if args.pid_file:
        write_pid_file(args.pid_file)
    VagrantStatusMonitor(args)
    # to respond to signals promptly
    signal.pause()


if __name__ == '__main__':
    main()
