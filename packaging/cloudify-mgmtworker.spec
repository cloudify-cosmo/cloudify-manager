# psycopg2 ships with its own required shared libraries
%global __requires_exclude_from site-packages/psycopg2
%global __provides_exclude_from site-packages/psycopg2

Name:           cloudify-management-worker
Version:        %{CLOUDIFY_VERSION}
Release:        %{CLOUDIFY_PACKAGE_RELEASE}%{?dist}
Summary:        Cloudify's Management Worker
Group:          Applications/Multimedia
License:        Apache 2.0
URL:            https://github.com/cloudify-cosmo/cloudify-manager
Vendor:         Cloudify Platform Ltd.
Packager:       Cloudify Platform Ltd.

BuildRequires:  python >= 2.7, python-virtualenv, openssl-devel, git
Requires:       python >= 2.7
Requires(pre):  shadow-utils


%description
Cloudify's Management worker


%build
virtualenv /opt/mgmtworker/env
/opt/mgmtworker/env/bin/pip install --upgrade pip setuptools
/opt/mgmtworker/env/bin/pip install https://github.com/cloudify-cosmo/cloudify-rest-client/archive/master.zip
/opt/mgmtworker/env/bin/pip install https://github.com/cloudify-cosmo/cloudify-plugins-common/archive/master.zip
/opt/mgmtworker/env/bin/pip install https://github.com/cloudify-cosmo/cloudify-script-plugin/archive/master.zip
/opt/mgmtworker/env/bin/pip install https://github.com/cloudify-cosmo/cloudify-agent/archive/CY-199-celery-replacement.zip
/opt/mgmtworker/env/bin/pip install --upgrade "${RPM_SOURCE_DIR}/plugins/riemann-controller"
/opt/mgmtworker/env/bin/pip install --upgrade "${RPM_SOURCE_DIR}/workflows"
rm /opt/mgmtworker/env/lib/python2.7/site-packages/zmq/tests/_test_asyncio.py


%install
mkdir -p %{buildroot}/opt/mgmtworker
mv /opt/mgmtworker/env %{buildroot}/opt/mgmtworker
mkdir -p %{buildroot}/var/log/cloudify/mgmtworker
mkdir -p %{buildroot}/opt/mgmtworker/config
mkdir -p %{buildroot}/opt/mgmtworker/work
mkdir -p %{buildroot}/opt/mgmtworker/env/plugins

cp -R ${RPM_SOURCE_DIR}/packaging/mgmtworker/files/* %{buildroot}


%pre
groupadd -fr cfyuser
getent passwd cfyuser >/dev/null || useradd -r -g cfyuser -d /etc/cloudify -s /sbin/nologin cfyuser


%files
%defattr(-,root,root)
/etc/cloudify/logging.conf
/etc/logrotate.d/cloudify-mgmtworker
/usr/lib/systemd/system/cloudify-mgmtworker.service
%attr(750,cfyuser,cfyuser) /opt/mgmtworker/config
%attr(750,cfyuser,cfyuser) /opt/mgmtworker/work
%attr(750,cfyuser,cfyuser) /opt/mgmtworker/env/plugins
/opt/mgmtworker
%attr(750,cfyuser,adm) /var/log/cloudify/mgmtworker
