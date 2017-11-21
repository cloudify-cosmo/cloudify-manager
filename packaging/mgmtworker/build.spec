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
/opt/manager/env/bin/pip install git+https://github.com/cloudify-cosmo/cloudify-rest-client@4.2#egg=cloudify-rest-client==4.2
/opt/manager/env/bin/pip install git+https://github.com/cloudify-cosmo/cloudify-plugins-common@4.2#egg=cloudify-plugins-common==4.2
/opt/manager/env/bin/pip install git+https://github.com/cloudify-cosmo/cloudify-script-plugin
/opt/manager/env/bin/pip install git+https://github.com/cloudify-cosmo/cloudify-agent@4.2#egg=cloudify-agent==4.2
/opt/manager/env/bin/pip install psycopg2
/opt/manager/env/bin/pip install --upgrade "${RPM_SOURCE_DIR}/plugins/riemann-controller"
/opt/manager/env/bin/pip install --upgrade "${RPM_SOURCE_DIR}/workflows"

%install

mkdir -p %{buildroot}/opt/mgmtworker
mv /opt/mgmtworker/env %{buildroot}/opt/manager

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
