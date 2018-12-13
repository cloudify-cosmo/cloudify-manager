########
# Copyright (c) 2018 Cloudify Platform Ltd. All rights reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from io import StringIO

# TODO: Write Ubuntu Wagon Builder Image Dockerfile.

# flake8: noqa

centos_content = """FROM amd64/centos:latest
MAINTAINER Cosmo (hello@cloudify.co)
WORKDIR /build
RUN echo "manylinux1_compatible = False" > "/usr/lib64/python2.7/_manylinux.py"
RUN yum -y install python-devel gcc openssl git libxslt-devel libxml2-devel openldap-devel libffi-devel openssl-devel libvirt-devel
RUN curl "https://bootstrap.pypa.io/get-pip.py" -o "get-pip.py"
RUN python get-pip.py
RUN pip install --upgrade pip==9.0.1
RUN pip install wagon==0.3.2
ENTRYPOINT ["wagon"]
CMD ["create", "-s", ".", "-v", "-f"]"""


class DockerfileIO(StringIO):

    @property
    def name(self):
        return 'Dockerfile'


centos = DockerfileIO(unicode(centos_content))
