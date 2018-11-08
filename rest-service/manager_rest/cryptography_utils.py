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

import base64
import json
import os

from cryptography.fernet import Fernet

from manager_rest.constants import SECURITY_FILE_LOCATION


def encrypt(data, key=None):
    key = key or _get_encryption_key()
    fernet = Fernet256(str(key))
    return fernet.encrypt(bytes(data))


def decrypt(encrypted_data, key=None):
    key = key or _get_encryption_key()
    fernet = Fernet256(str(key))
    return fernet.decrypt(bytes(encrypted_data))


def decrypt128(encrypted_data, key=None):
    key = key or _get_encryption_key()
    fernet = Fernet(str(key))
    return fernet.decrypt(bytes(encrypted_data))


def _get_encryption_key():
    # We should have used config.instance.security_encryption_key to get the
    # key, but in snapshot restore the encryption key get updated in the
    # config file (rest-security.conf) but not in the memory. This is a temp
    # solution until we will have dynamic configuration mechanism
    with open(SECURITY_FILE_LOCATION) as security_conf_file:
        rest_security_conf = json.load(security_conf_file)
        return rest_security_conf['encryption_key']


class Fernet256(Fernet):
    def __init__(self, key, **kwargs):
        super(Fernet256, self).__init__(Fernet.generate_key(), **kwargs)
        key = base64.urlsafe_b64decode(key)
        if len(key) != 64:
            raise ValueError(
                "Fernet256 key must be 64 url-safe base64-encoded bytes."
            )

        self._signing_key = key[:32]
        self._encryption_key = key[32:]

    @classmethod
    def generate_key(cls):
        return base64.urlsafe_b64encode(os.urandom(64))
