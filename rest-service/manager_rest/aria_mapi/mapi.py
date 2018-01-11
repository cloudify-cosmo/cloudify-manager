########
# Copyright (c) 2017 GigaSpaces Technologies Ltd. All rights reserved
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
import json
import pickle
import datetime
from functools import partial

import requests
from aria.storage import api

from . import (
    wrappers,
    exceptions
)


class _DateTimeEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (datetime.date, datetime.datetime)):
            return obj.isoformat()
        else:
            return super(_DateTimeEncoder, self).default(obj)



class RESTMAPI(api.ModelAPI):

    def __init__(self, host, port, api_endpoint, *args, **kwargs):
        super(RESTMAPI, self).__init__(*args, **kwargs)
        self._endpoint = '{host}:{port}/{api_endpoint}'.format(
            host=host, port=port, api_endpoint=api_endpoint)
        # Used by the operation context itself, we should probably create a
        # `close` method per mapi instead.
        self._session = type(
            'MockSession', (object,), {'remove': lambda *a, **kw: None})()
        self._engine = type(
            'MockEngine', (object,), {'dispose': lambda *a, **kw: None})()

    def put(self, entry, **kwargs):
        response = requests.put(
            '/'.join([self._endpoint, self.name]),
            data=pickle.dumps(
                entry._obj
                if isinstance(entry, wrappers.WrapperBase)
                else entry)
        )
        return self._respond(response, attribute_path=self.name)

    def create(self, **kwargs):
        pass

    def get(self, entry_id, **kwargs):
        suffix = '/'.join([self.name, str(entry_id)])
        response = requests.get('/'.join([self._endpoint, suffix]), json=kwargs)
        return self._respond(response, attribute_path=suffix)

    def refresh(self, entry, _include=None):
        updated_entry = self.get(entry.id, _include=_include)
        return entry._update(updated_entry)

    def iter(self, **kwargs):
        response = requests.get('/'.join([self._endpoint, self.name]),
                                json=kwargs)
        for item in self._respond(response, attribute_path=self.name):
            yield item

    def update(self, entry, **kwargs):
        suffix = '/'.join([self.name, str(entry.id)])
        response = requests.patch(
            '/'.join([self._endpoint, suffix]),
            data=pickle.dumps(
                {key: getattr(entry, key) for key in entry._dirty}
            )
        )
        # Clear the changes
        entry._clear()
        return self._respond(response, attribute_path=suffix)

    def _respond(self, response, attribute_path):
        try:
            return self._wrap(pickle.loads(response.json()), attribute_path)
        except Exception:
            raise exceptions.RequestException(response.text)

    def _wrap(self, value, attribute_path):
        wrapper = None
        kw = {}

        if isinstance(value, dict):
            wrapper = wrappers.ModelWrapper
            kw = dict(obj=value)
        elif isinstance(value, list):
            wrapper = wrappers.ListWrapper
            seq = [self._wrap(item, '/'.join([attribute_path, str(i)]))
                   for i, item in enumerate(value)]
            kw = dict(seq=seq)

        if callable(wrapper):
            return wrapper(
                _attribute_path=attribute_path,
                _query=partial(self._get_query,
                               end_point=self._endpoint,
                               responder=self._respond),
                **kw
            )

        return value

    @classmethod
    def _get_query(cls, entry_path, end_point, responder):
        """
        Enables sending generic queries to the rest service

        :param entry_path: The path of the attribute.
        :param end_point: The rest service endpoint.
        :param responder: The responder method to wrap with
        :return:
        """
        response = requests.get('/'.join([end_point, entry_path]))
        return responder(response, entry_path)
