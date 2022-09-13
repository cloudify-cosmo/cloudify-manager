#########
# Copyright (c) 2016 GigaSpaces Technologies Ltd. All rights reserved
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


def generate_progress_func(total_size, buffer_size=8192):
    """Generate a function that helps test upload/download progress

    :param total_size: Total size of the file to upload/download
    :param buffer_size: Size of chunk
    :return: A function that receives 2 ints - number of bytes read so far,
    and the total size in bytes
    """
    # Wrap the integer in a list, to allow mutating it inside the inner func
    iteration = [0]
    max_iterations = total_size // buffer_size

    def print_progress(watcher):
        read_bytes, total_bytes = watcher.bytes_read, watcher.len

        i = iteration[0]
        assert read_bytes == total_bytes

        expected_read_value = buffer_size * (i + 1)
        if i < max_iterations:
            assert read_bytes == expected_read_value
        else:
            assert read_bytes == total_bytes

        iteration[0] += 1

    return print_progress
