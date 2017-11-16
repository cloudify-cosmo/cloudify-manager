
Name:           cloudify-rest-service
Version:        4.2
Release:        1%{?dist}
Summary:        Cloudify's REST Service
Group:          Applications/Multimedia
License:        Apache 2.0
URL:            https://github.com/cloudify-cosmo/cloudify-manager
Vendor:         Gigaspaces Inc.
Packager:       Gigaspaces Inc.

BuildRequires:  python >= 2.7, python-virtualenv, openssl-devel, postgresql-devel, openldap-devel, git
Requires:       python >= 2.7, postgresql-libs, nginx >= 1.12
Requires(pre):  shadow-utils



%description
Cloudify's REST Service.



%prep


%build

virtualenv /opt/manager/env

default_version=%{CORE_BRANCH}
export REST_SERVICE_BUILD=True

/opt/manager/env/bin/pip install --upgrade pip setuptools
/opt/manager/env/bin/pip install git+https://github.com/cloudify-cosmo/cloudify-dsl-parser@4.2#egg=cloudify-dsl-parser==4.2
/opt/manager/env/bin/pip install --upgrade "${RPM_SOURCE_DIR}/rest-service"

if [ "%{REPO}" != "cloudify-versions" ]; then
    /opt/manager/env/bin/pip install https://%{GITHUB_USERNAME}:%{GITHUB_PASSWORD}@github.com/cloudify-cosmo/cloudify-premium/archive/%{CORE_BRANCH}.tar.gz
fi


%install

mkdir -p %{buildroot}/opt/manager
mv /opt/manager/env %{buildroot}/opt/manager

mkdir -p %{buildroot}/opt/manager/resources/
cp -R "${RPM_SOURCE_DIR}/resources/rest-service/cloudify/" "%{buildroot}/opt/manager/resources/"


%pre

groupadd -fr cfyuser
getent passwd cfyuser >/dev/null || useradd -r -g cfyuser -d /etc/cloudify -s /sbin/nologin cfyuser


%post

export REST_SERVICE_BUILD=True

if [ ! -d "/opt/manager/env" ]; then virtualenv --no-download /opt/manager/env; fi && \
if [ "%{REPO}" != "cloudify-versions" ]; then
    /opt/manager/env/bin/pip install --upgrade --force-reinstall --use-wheel --no-index --find-links=/var/wheels/%{name} cloudify-premium --pre
fi
# sudo cp -R "/tmp/resources/rest-service/cloudify/" "/opt/manager/resources/"


%preun
%postun


%files

%defattr(-,root,root)
/opt/manager

%dir %attr(-,cfyuser,adm,750) /var/log/cloudify/rest
