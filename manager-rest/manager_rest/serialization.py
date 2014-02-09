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

__author__ = 'ran'

import json

TYPE_FIELD_NAME = '_type'
DATA_FIELD_NAME = 'data'


def serialize_object(obj):
    if isinstance(obj, dict):
        return {key: serialize_object(val) for key, val
                in obj.iteritems()}
    if isinstance(obj, list):
        return [serialize_object(val) for val in obj]

    if hasattr(obj, 'to_dict'):
        obj_data = obj.to_dict()
        obj_data_with_meta = {
            TYPE_FIELD_NAME: '{0}.{1}'.format(obj.__class__.__module__,
                                              obj.__class__.__name__),
            DATA_FIELD_NAME: obj_data
        }
        return obj_data_with_meta
    return obj


def deserialize_object(obj):
    if isinstance(obj, list):
        return [deserialize_object(val) for val in obj]

    if isinstance(obj, dict):
        if TYPE_FIELD_NAME in obj:
            #nested object
            obj_type = obj[TYPE_FIELD_NAME]
            obj_class_name = obj_type.split('.')[-1]
            obj_module_name = obj_type[:len(obj_type)-len(obj_class_name)-1]
            if '.' in obj_module_name:
                module = __import__(obj_module_name,
                                    fromlist=obj_module_name.split('.')[-1])
            else:
                module = __import__(obj_module_name)
            cls = getattr(module, obj_class_name)
            return cls().from_dict(obj[DATA_FIELD_NAME])
        return {key: deserialize_object(val) for key, val
                in obj.iteritems()}

    return obj


def to_json(obj):
    return json.dumps(serialize_object(obj))


def from_json(json_data):
    return deserialize_object(json.loads(json_data))


class SerializableObjectBase(object):

    """
        Base class for objects which require serialization/deserialization
        capabilities. When inheriting from this class, you must ensure the
        derived class has a "default constructor", i.e. one which receives
        no parameters and declares all of the member's fields.

        Override to_dict and from_dict methods to implement specific class
        serialization/deserialization logic if necessary.
        Note that custom class fields will get serialized as well. To avoid
        this, you may override the _get_instance_attr_to_value method.
    """

    def to_dict(self):
        instance_attr_to_value = self._get_instance_attr_to_value()
        data = serialize_object(instance_attr_to_value)
        return data

    @classmethod
    def from_dict(cls, data):
        obj = cls()

        instance_attrs = [attr for attr, _
                          in obj._get_instance_attr_to_value().iteritems()]
        for attr in instance_attrs:
            if attr in data:
                val = deserialize_object(data[attr])
                setattr(obj, attr, val)
        return obj

    def to_json(self):
        return json.dumps(self.to_dict())

    @classmethod
    def from_json(cls, json_data):
        return cls.from_dict(json.loads(json_data))

    def _get_instance_attr_to_value(self):
        attr_and_values = ((attr, getattr(self, attr)) for attr in dir(self)
                           if not attr.startswith("__"))
        instance_attr_to_values = {attr: value for attr, value in
                                   attr_and_values if not callable(value)
                                   and not attr == 'resource_fields'}
        return instance_attr_to_values
