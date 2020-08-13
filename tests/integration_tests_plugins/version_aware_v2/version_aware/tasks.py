########
# Copyright (c) 2013 GigaSpaces Technologies Ltd. All rights reserved
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

import sys
from cloudify import ctx as op_ctx
from cloudify.decorators import workflow, operation

VERSION = '2.0'
MESSAGE = '{0} [{1}]'.format(VERSION, sys.executable)


@workflow
def cda_wf(ctx, **_):
    ctx.logger.info('CDA Workflow {0}'.format(MESSAGE))


@workflow
def run_cda_op(ctx, **_):
    instance = list(ctx.get_node('node').instances)[0]
    instance.execute_operation('test_cda.cda_op').get()


@workflow
def run_host_op(ctx, **_):
    instance = list(ctx.get_node('node').instances)[0]
    instance.execute_operation('test_host.host_op').get()


@operation
def cda_op(**_):
    op_ctx.logger.info('CDA Operation {0}'.format(MESSAGE))
    op_ctx.instance.runtime_properties['cda_op'] = VERSION


@operation
def host_op(**_):
    op_ctx.logger.info('Host Operation {0}'.format(MESSAGE))
    op_ctx.instance.runtime_properties['host_op'] = VERSION
