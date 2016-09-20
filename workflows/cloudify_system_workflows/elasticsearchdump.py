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
import utils

from cloudify.workflows import ctx


class ElasticSearchDump(object):

    def restore_prev_4(self, tempdir):
        ctx.logger.debug('Restoring es from version previous to 4')
        python_bin = '/opt/manager/env/bin/python'
        dir_path = os.path.dirname(os.path.realpath(__file__))
        script_path = os.path.join(dir_path, 'estopg.py')
        es_dump_path = os.path.join(tempdir, 'es_data')
        result = utils.run([python_bin, script_path, es_dump_path])
        if result and hasattr(result, 'aggr_stdout'):
            ctx.logger.debug('Process result: \n{0}'
                             .format(result.aggr_stdout))
        return True
