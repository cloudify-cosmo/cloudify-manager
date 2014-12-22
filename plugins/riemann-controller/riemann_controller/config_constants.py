#########
# Copyright (c) 2014 GigaSpaces Technologies Ltd. All rights reserved
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


class Constants:
    """ Constants that can be used in policies """
    PERIODICAL_EXPIRATION_INTERVAL = 5  # in seconds
    TRIGGERING_STATE = "triggering_state"
    STABLE_STATE = "ok"
    HEART_BEAT_FAILURE = "heart-beat-failure"
    MIN_INTERVAL_BETWEEN_WORKFLOWS = 5
