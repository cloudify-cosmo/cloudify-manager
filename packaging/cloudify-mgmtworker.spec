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

BuildRequires:  python >= 2.7, python-virtualenv, openssl-devel, postgresql-devel, git
Requires:       python >= 2.7, postgresql-libs
Requires(pre):  shadow-utils




%description
Cloudify's Management worker



%prep
%build

virtualenv /opt/mgmtworker/env

/opt/mgmtworker/env/bin/pip install --upgrade pip setuptools
/opt/mgmtworker/env/bin/pip install git+https://github.com/cloudify-cosmo/cloudify-rest-client
/opt/mgmtworker/env/bin/pip install git+https://github.com/cloudify-cosmo/cloudify-plugins-common
/opt/mgmtworker/env/bin/pip install git+https://github.com/cloudify-cosmo/cloudify-script-plugin
/opt/mgmtworker/env/bin/pip install git+https://github.com/cloudify-cosmo/cloudify-agent
/opt/mgmtworker/env/bin/pip install psycopg2
/opt/mgmtworker/env/bin/pip install --upgrade "${RPM_SOURCE_DIR}/plugins/riemann-controller"
/opt/mgmtworker/env/bin/pip install --upgrade "${RPM_SOURCE_DIR}/workflows"

rm /opt/mgmtworker/env/lib/python2.7/site-packages/zmq/tests/_test_asyncio.py

%install

mkdir -p %{buildroot}/opt/mgmtworker
mv /opt/mgmtworker/env %{buildroot}/opt/mgmtworker

# Create the log dir
mkdir -p %{buildroot}/var/log/cloudify/mgmtworker


%pre
groupadd -fr cfyuser
getent passwd cfyuser >/dev/null || useradd -r -g cfyuser -d /etc/cloudify -s /sbin/nologin cfyuser

%post

%preun
%postun

%files

%defattr(-,root,root)
/opt/mgmtworker

%attr(750,cfyuser,adm) /var/log/cloudify/mgmtworker
