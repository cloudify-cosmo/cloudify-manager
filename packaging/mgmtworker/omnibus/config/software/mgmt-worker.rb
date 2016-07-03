#
# Copyright 2015 YOUR NAME
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

# These options are required for all software definitions
name "cloudify-mgmt-worker"

ENV['CORE_TAG_NAME'] || raise('CORE_TAG_NAME environment variable not set')
default_version ENV['CORE_TAG_NAME']
dependency "python"
dependency "pip"
dependency "rest-client"
dependency "plugins-common"
dependency "script-plugin"
dependency "cloudify-agent"

source git: "https://github.com/cloudify-cosmo/cloudify-manager"

build do
    command ["#{install_dir}/embedded/bin/pip",
             "install", "--build=#{project_dir}", "./workflows/"]
    command ["#{install_dir}/embedded/bin/pip",
             "install", "--build=#{project_dir}/riemann", "./plugins/riemann-controller/"]
    command ["#{install_dir}/embedded/bin/pip",
             "install", "--build=#{project_dir}/dev-requirements",
             "-r", "./workflows/dev-requirements.txt"]
    command ["#{install_dir}/embedded/bin/pip",
             "install", "https://github.com/cloudify-cosmo/wagon/archive/0.3.1.zip"]
    command ["#{install_dir}/embedded/bin/pip",
             "install", "psutil==2.1.1"]
end

