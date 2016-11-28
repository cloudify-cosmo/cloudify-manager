########
# Copyright (c) 2015 GigaSpaces Technologies Ltd. All rights reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
#    * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    * See the License for the specific language governing permissions and
#    * limitations under the License.

import os
import json
import subprocess

from cloudify.exceptions import NonRecoverableError


class InfluxDB(object):
    _INFLUXDB = 'influxdb_data'
    _INFLUXDB_DUMP_CMD = ('curl -s -G "http://localhost:8086/db/cloudify/series'  # NOQA
                          '?u=root&p=root&chunked=true" --data-urlencode'
                          ' "q=select * from /.*/" > {0}')
    _INFLUXDB_RESTORE_CMD = ('cat {0} | while read -r line; do curl -X POST '
                             '-d "[${{line}}]" "http://localhost:8086/db/cloudify/'  # NOQA
                             'series?u=root&p=root" ;done')

    @staticmethod
    def restore(tempdir):
        influxdb_f = os.path.join(tempdir, InfluxDB._INFLUXDB)
        if os.path.exists(influxdb_f):
            return_code = subprocess.call(
                InfluxDB._INFLUXDB_RESTORE_CMD.format(influxdb_f),
                shell=True
            )
            if return_code != 0:
                raise NonRecoverableError(
                    'Error during restoring InfluxDB data, '
                    'error code: {0}'.format(return_code)
                )

    @staticmethod
    def dump(tempdir):
        influxdb_file = os.path.join(tempdir, InfluxDB._INFLUXDB)
        influxdb_temp_file = influxdb_file + '.temp'
        return_code = subprocess.call(
            InfluxDB._INFLUXDB_DUMP_CMD.format(influxdb_temp_file),
            shell=True
        )
        if return_code != 0:
            raise NonRecoverableError('Error during dumping InfluxDB data, '
                                      'error code: {0}'.format(return_code))
        with open(influxdb_temp_file, 'r') as f, open(influxdb_file, 'w') as g:
            for obj in InfluxDB._get_json_objects(f):
                g.write(obj + os.linesep)

        os.remove(influxdb_temp_file)

    @staticmethod
    def _get_json_objects(f):
        def chunks(g):
            ch = g.read(10000)
            yield ch
            while ch:
                ch = g.read(10000)
                yield ch

        s = ''
        n = 0
        decoder = json.JSONDecoder()
        for ch in chunks(f):
            s += ch
            try:
                while s:
                    obj, idx = decoder.raw_decode(s)
                    n += 1
                    yield json.dumps(obj)
                    s = s[idx:]
            except:
                pass

        # assert not n or not s
        # not (not n or not s) -> n and s
        if n and s:
            raise NonRecoverableError('Error during converting InfluxDB dump '
                                      'data to data appropriate for snapshot.')
