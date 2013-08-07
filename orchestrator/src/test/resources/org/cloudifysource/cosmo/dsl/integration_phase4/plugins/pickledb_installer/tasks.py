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

from cosmo.celery import celery
import tempfile
from os import path
import pickledb


@celery.task
def install(**kwargs):
	pass


@celery.task
def start(db_name='pickle', db_data={}, **kwargs):
    db_file = get_db_file_location(db_name)
    db = pickledb.load(db_file, False)
    for key, value in db_data.iteritems():
    	db.set(key, value)
    db.dump()


@celery.task
def get_db_file_location(db_name, **kwargs):
    return path.join(tempfile.gettempdir(), "{0}.db".format(db_name))


def test():
	db_name = 'pickle'
	db_data = {'key1': 'value1', 'key2': 'value2'}
	start(db_name, db_data)
	db_file = get_db_file_location(db_name)
	db = pickledb.load(db_file, False)
	print(db.get('key1'))
	print(db.get('key2'))
	print(get_db_file_location(db_name))

