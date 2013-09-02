#/*******************************************************************************
# * Copyright (c) 2013 GigaSpaces Technologies Ltd. All rights reserved
# *
# * Licensed under the Apache License, Version 2.0 (the "License");
# * you may not use this file except in compliance with the License.
# * You may obtain a copy of the License at
# *
# *       http://www.apache.org/licenses/LICENSE-2.0
# *
# * Unless required by applicable law or agreed to in writing, software
# * distributed under the License is distributed on an "AS IS" BASIS,
#    * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    * See the License for the specific language governing permissions and
#    * limitations under the License.
# *******************************************************************************/

import urllib
import urllib2

from cosmo.celery import celery


@celery.task
def set_db_properties(db_file, port=8080, **kwargs):
    url = "http://localhost:{0}/admin".format(port)
    data = urllib.urlencode({"db_file": db_file})
    request = urllib2.Request(url, data)
    request.get_method = lambda: 'PUT'
    response = urllib2.urlopen(request)
    if response.getcode() != 200:
        raise RuntimeError("request [{0}] return code is: {1}".format(request, response.getcode()))


