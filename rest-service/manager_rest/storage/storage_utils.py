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

from manager_rest.storage.models import Node
from manager_rest.storage import db, get_storage_manager
from manager_rest.manager_exceptions import NotFoundError


def get_node(deployment_id, node_id):
    """Return the single node associated with a given ID and Dep ID
    """
    nodes = get_storage_manager().list(
        Node,
        filters={'deployment_id': deployment_id, 'id': node_id}
    )
    if not nodes:
        raise NotFoundError(
            'Requested Node with ID `{0}` on Deployment `{1}` '
            'was not found'.format(node_id, deployment_id)
        )
    return nodes[0]


def try_acquire_lock_on_table(lock_number):
    # make sure a flask app exists before calling this function
    results = db.session.execute('SELECT pg_try_advisory_lock(:lock_number)',
                                 {'lock_number': lock_number})
    return results.first()[0]


def unlock_table(lock_number):
    # make sure a flask app exists before calling this function
    db.session.execute('SELECT pg_advisory_unlock(:lock_number)',
                       {'lock_number': lock_number})
