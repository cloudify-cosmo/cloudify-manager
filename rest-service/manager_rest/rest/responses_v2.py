#########
# Copyright (c) 2015 GigaSpaces Technologies Ltd. All rights reserved
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
#
from typing import Optional, Sequence

from flask_restful import fields
from flask_restful_swagger import swagger


@swagger.model
class ListResponse(object):
    resource_fields = {
        'metadata': fields.Raw,
        'items': fields.List(fields.Raw)}

    items: Optional[Sequence]

    def __init__(self, **kwargs):
        self.metadata = kwargs.get('metadata')
        self.items = kwargs.get('items')

    def __len__(self):
        if self.items is None:
            return 0
        return len(self.items)

    def __iter__(self):
        if self.items is None:
            return iter([])
        return iter(self.items)
