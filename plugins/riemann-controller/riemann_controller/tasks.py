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


import time

import bernhard

from cloudify.decorators import operation


@operation
def create(ctx, **kwargs):
    bernhard.Client().send({
        'host': 'localhost',
        'service': 'service',
        'state': 'state',
        'description': 'description',
        'time': int(time.time()),
    })


@operation
def delete(ctx, **kwargs):
    pass
