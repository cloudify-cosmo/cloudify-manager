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
from functools import wraps, partial

from flask import (
    request,
)

from aria.modeling.mixins import ModelMixin
from .. import base


def _wrap(value):
    if isinstance(value, ModelMixin):
        fields_dict = value.to_dict(
            fields=(
                request.json.get('_include')
                if request.json else None
            )
        )
        # This is used to compare classes
        fields_dict['__cls_name__'] = value.__class__.__name__
        return fields_dict
    elif isinstance(value, list):
        return [_wrap(i) for i in value]
    elif isinstance(value, dict):
        return {k: _wrap(v) for k, v in value.items()}
    return value


def _callable_wrapper(return_value):
    return return_value


def _jsonify(func):
    @wraps(func)
    def _wrapper(*args, **kwargs):
        return_value = func(*args, **kwargs)
        if callable(return_value):
            import pydevd; pydevd.settrace('192.168.9.239', suspend=True, port=53101)
            # If it's a method call return an empty lambda
            return pickle.dumps(partial(_callable_wrapper, _wrap(return_value())))
        else:
            return pickle.dumps(_wrap(return_value))
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

        return entity_handler.list(**(request.json if request.data else {}))

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

        for key, value in updated_entity.items():
            setattr(entity, key, value)

        entity_handler.update(entity)

        return entity

    @_jsonify
    def put(self, path):
        entity_name, _ = self._split_path(path)
        entity_handler = getattr(self.model, entity_name)
        entity_cls = entity_handler.model_cls
        return entity_handler.put(entity_cls(request.data))

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
                    except AttributeError:
                        raise Exception("Invalid path: {path}".format(
                            path=path))
        return current_entity
