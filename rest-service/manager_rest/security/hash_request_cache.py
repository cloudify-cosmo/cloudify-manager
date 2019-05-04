########
# Copyright (c) 2019 Cloudify Platform Ltd. All rights reserved
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

from cachetools import TTLCache


class HashVerifyRequestCache(object):
    def __init__(self):
        ttl = 60 * 5
        max_size = 500
        self._cache = TTLCache(max_size, ttl)

    def cache_verify_hash_result(self, token, user_id):
        self._cache[(user_id, token)] = True

    def get_verify_hash_result(self, token, user_id):
        cache_key = (user_id, token)
        if cache_key in self._cache:
            # If valid, extending cache TTL for supporting active users
            self._cache[cache_key] = True
            return True

        return False
