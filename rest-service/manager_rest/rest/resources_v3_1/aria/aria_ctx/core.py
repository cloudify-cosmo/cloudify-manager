#########
# Copyright (c) 2017 GigaSpaces Technologies Ltd. All rights reserved
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
import pickle
from functools import wraps

from flask import (
    request,
    jsonify
)

from .. import base


def _jsonify(func):
    @wraps(func)
    def _wrapper(*args, **kwargs):
        return jsonify(pickle.dumps(func(*args, **kwargs)))

    return _wrapper


class Core(base.BaseARIAEndpoints):
    @_jsonify
    def get(self, path):
        entity_name, entity_path = self._split_path(path)
        entity_handler = getattr(self.model, entity_name)
        if entity_path:
            entity_id, attribute_path = self._split_path(entity_path)
            entity = entity_handler.get(entity_id)
            return self._traverse_entity(entity, attribute_path)

        return entity_handler.list(**request.json)

    @_jsonify
    def patch(self, path):
        entity_name, entity_path = self._split_path(path)
        entity_handler = getattr(self.model, entity_name)
        entity_id, attribute_path = self._split_path(entity_path)
        entity = self._traverse_entity(
            entity_handler.get(entity_id),
            attribute_path
        )

        updated_entity = pickle.loads(request.data)

        for key in updated_entity._sa_instance_state.committed_state:
            setattr(entity, key, getattr(updated_entity, key))

        entity_handler.update(entity)

        return entity

    @_jsonify
    def put(self, path):
        entity_name, _ = self._split_path(path)
        entity_handler = getattr(self.model, entity_name)
        return entity_handler.put(pickle.loads(request.data))

    @staticmethod
    def _split_path(path):
        return path.split('/', 1) if '/' in path else (path, '')

    @staticmethod
    def _traverse_entity(entity, path):
        current_entity = entity
        for key in path.split('/'):
            if key:
                if isinstance(current_entity, dict):
                    current_entity = current_entity[key]
                elif isinstance(current_entity, list):
                    current_entity = current_entity[int(key)]
                else:
                    try:
                        current_entity = getattr(current_entity, key)
                        if callable(current_entity):
                            current_entity = current_entity()
                    except AttributeError:
                        raise Exception("Invalid path")
        return current_entity
