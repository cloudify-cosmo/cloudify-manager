%define _rpmdir /tmp


Name:           cloudify-rest-service
Version:        %{VERSION}
Release:        %{PRERELEASE}
Summary:        Cloudify's REST Service
Group:          Applications/Multimedia
License:        Apache 2.0
URL:            https://github.com/cloudify-cosmo/cloudify-manager
Vendor:         Gigaspaces Inc.
Prefix:         %{_prefix}
Packager:       Gigaspaces Inc.

Requires:       postgresql-libs, nginx >= 1.12
Requires(pre):  shadow-utils



%description
Cloudify's REST Service.



%prep

set +e
pip=$(which pip)
set -e

[ ! -z $pip ] || curl --show-error --silent --retry 5 https://bootstrap.pypa.io/get-pip.py | python
pip install virtualenv


%build

virtualenv /opt/manager/env


%install

export REST_SERVICE_BUILD=True
default_version=%{CORE_BRANCH}

mkdir -p %{buildroot}/opt/manager/resources/
sudo cp -R "/tmp/resources/rest-service/cloudify/" "%{buildroot}/opt/manager/resources/"

# ldappy is being install without a specific version, until it'll be stable..

sudo /tmp/env/bin/pip wheel virtualenv --wheel-dir %{buildroot}/var/wheels/%{name} && \
sudo /tmp/env/bin/pip wheel --wheel-dir=%{buildroot}/var/wheels/%{name} --find-links=%{buildroot}/var/wheels/%{name} https://github.com/dusking/ldappy/archive/master.tar.gz && \
if [ "%{REPO}" != "cloudify-versions" ]; then
    sudo /tmp/env/bin/pip wheel --wheel-dir=%{buildroot}/var/wheels/%{name} --find-links=%{buildroot}/var/wheels/%{name} https://%{GITHUB_USERNAME}:%{GITHUB_PASSWORD}@github.com/cloudify-cosmo/cloudify-premium/archive/%{CORE_BRANCH}.tar.gz
fi
sudo -E /tmp/env/bin/pip wheel --wheel-dir=%{buildroot}/var/wheels/%{name} --find-links=%{buildroot}/var/wheels/%{name} /tmp/rest-service


%pre

groupadd -fr cfyuser
getent passwd cfyuser >/dev/null || useradd -r -g cfyuser -d /etc/cloudify -s /sbin/nologin cfyuser


%post

export REST_SERVICE_BUILD=True

if [ ! -d "/opt/manager/env" ]; then virtualenv --no-download /opt/manager/env; fi && \
/opt/manager/env/bin/pip install --upgrade --force-reinstall --use-wheel --no-index --find-links=/var/wheels/%{name} ldappy --pre && \
if [ "%{REPO}" != "cloudify-versions" ]; then
    /opt/manager/env/bin/pip install --upgrade --force-reinstall --use-wheel --no-index --find-links=/var/wheels/%{name} cloudify-premium --pre
fi
# sudo cp -R "/tmp/resources/rest-service/cloudify/" "/opt/manager/resources/"


%preun
%postun

rm -rf /opt/manager/resources
rm -rf /var/wheels/${name}


%files

%defattr(-,root,root)
/opt/manager

%dir %attr(-,cfyuser,adm,750) /var/log/cloudify/rest
