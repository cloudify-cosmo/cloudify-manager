#########
# Copyright (c) 2017-2019 Cloudify Platform Ltd. All rights reserved
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

from flask_restful import Resource

from cloudify.snapshots import STATES

from ..rest_utils import is_system_in_snapshot_restore_process


class SnapshotsStatus(Resource):
    """
    Note that this class is 'Resource' and not 'SecuredResource' since we
    want it to work during the entire time of snapshot restore, even when
    authentication is not possible.
    """
    def get(self):
        """"
        While a snapshot is restored a temp file called
        `<unique-str>-snapshot-data` is created on the Manager. If the file
        does not exists it means there is no snapshot restore running.
        """
        if is_system_in_snapshot_restore_process():
            return {'status': STATES.RUNNING}
        return {'status': STATES.NOT_RUNNING}
