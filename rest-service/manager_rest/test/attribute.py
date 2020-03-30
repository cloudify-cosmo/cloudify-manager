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


def attr(*args, **kwargs):
    """Decorator that adds attributes to classes or functions
    for use with unit tests runner.
    """
    def wrapped(element):
        for name in args:
            setattr(element, name, True)
        for name, value in kwargs.items():
            setattr(element, name, value)
        return element
    return wrapped
