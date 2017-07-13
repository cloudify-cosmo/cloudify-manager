%define _rpmdir /tmp


Name:           cloudify-management-worker
Version:        %{VERSION}
Release:        %{PRERELEASE}
Summary:        Cloudify's Management Worker
Group:          Applications/Multimedia
License:        Apache 2.0
URL:            https://github.com/cloudify-cosmo/cloudify-manager
Vendor:         Gigaspaces Inc.
Prefix:         %{_prefix}
Packager:       Gigaspaces Inc.
BuildRoot:      %{_tmppath}/%{name}-root



%description
Cloudify's REST Service.



%prep

set +e
pip=$(which pip)
set -e

[ ! -z $pip ] || sudo curl --show-error --silent --retry 5 https://bootstrap.pypa.io/get-pip.py | sudo python
sudo yum install -y git python-devel postgresql-devel gcc gcc-c++
sudo pip install virtualenv
sudo virtualenv /tmp/env
sudo /tmp/env/bin/pip install setuptools==18.1 && \
sudo /tmp/env/bin/pip install wheel==0.24.0 && \

%build
%install

destination="/tmp/${RANDOM}.file"
curl --retry 10 --fail --silent --show-error --location https://github.com/cloudify-cosmo/cloudify-manager/archive/%{CORE_BRANCH}.tar.gz --create-dirs --output $destination && \
tar -xzf $destination --strip-components=1 -C "/tmp" && \

sudo /tmp/env/bin/pip wheel virtualenv --wheel-dir %{buildroot}/var/wheels/%{name} && \
sudo /tmp/env/bin/pip wheel --wheel-dir=%{buildroot}/var/wheels/%{name} --find-links=%{buildroot}/var/wheels/%{name} https://github.com/cloudify-cosmo/cloudify-rest-client/archive/%{CORE_BRANCH}.tar.gz && \
sudo /tmp/env/bin/pip wheel --wheel-dir=%{buildroot}/var/wheels/%{name} --find-links=%{buildroot}/var/wheels/%{name} https://github.com/cloudify-cosmo/cloudify-plugins-common/archive/%{CORE_BRANCH}.tar.gz && \
sudo /tmp/env/bin/pip wheel --wheel-dir=%{buildroot}/var/wheels/%{name} --find-links=%{buildroot}/var/wheels/%{name} https://github.com/cloudify-cosmo/cloudify-script-plugin/archive/1.4.tar.gz && \
sudo /tmp/env/bin/pip wheel --wheel-dir=%{buildroot}/var/wheels/%{name} --find-links=%{buildroot}/var/wheels/%{name} https://github.com/cloudify-cosmo/cloudify-agent/archive/%{CORE_BRANCH}.tar.gz && \
sudo /tmp/env/bin/pip wheel --wheel-dir=%{buildroot}/var/wheels/%{name} --find-links=%{buildroot}/var/wheels/%{name} https://github.com/psycopg/psycopg2/archive/2_6_2.tar.gz && \
sudo /tmp/env/bin/pip wheel --wheel-dir=%{buildroot}/var/wheels/%{name} --find-links=%{buildroot}/var/wheels/%{name} /tmp/plugins/riemann-controller
sudo /tmp/env/bin/pip wheel --wheel-dir=%{buildroot}/var/wheels/%{name} --find-links=%{buildroot}/var/wheels/%{name} /tmp/workflows




%pre
%post

pip install --use-wheel --no-index --find-links=/var/wheels/%{name} virtualenv && \
if [ ! -d "/opt/mgmtworker/env" ]; then virtualenv /opt/mgmtworker/env; fi && \
/opt/mgmtworker/env/bin/pip install --upgrade --force-reinstall --use-wheel --no-index --find-links=/var/wheels/%{name} cloudify-rest-client --pre && \
/opt/mgmtworker/env/bin/pip install --upgrade --force-reinstall --use-wheel --no-index --find-links=/var/wheels/%{name} cloudify-plugins-common --pre && \
/opt/mgmtworker/env/bin/pip install --upgrade --force-reinstall --use-wheel --no-index --find-links=/var/wheels/%{name} cloudify-script-plugin --pre && \
/opt/mgmtworker/env/bin/pip install --upgrade --force-reinstall --use-wheel --no-index --find-links=/var/wheels/%{name} cloudify-agent --pre && \
/opt/mgmtworker/env/bin/pip install --upgrade --force-reinstall --use-wheel --no-index --find-links=/var/wheels/%{name} psycopg2 --pre && \
/opt/mgmtworker/env/bin/pip install --upgrade --force-reinstall --use-wheel --no-index --find-links=/var/wheels/%{name} cloudify-riemann-controller-plugin --pre && \
/opt/mgmtworker/env/bin/pip install --upgrade --force-reinstall --use-wheel --no-index --find-links=/var/wheels/%{name} cloudify-workflows --pre





%preun
%postun

rm -rf /var/wheels/${name}


%files

%defattr(-,root,root)
/var/wheels/%{name}/*.whl