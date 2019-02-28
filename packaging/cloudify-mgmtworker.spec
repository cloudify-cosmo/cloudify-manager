%define _python_bytecompile_errors_terminate_build 0
%define __jar_repack %{nil}
%define PIP_INSTALL /opt/mgmtworker/env/bin/pip install -c "${RPM_SOURCE_DIR}/packaging/mgmtworker/constraints.txt"

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
BuildRequires:  postgresql-devel
Requires:       python >= 2.7, postgresql-libs
Requires(pre):  shadow-utils

%description
Cloudify's Management worker


%build
virtualenv /opt/mgmtworker/env
%{PIP_INSTALL} --upgrade pip setuptools
%{PIP_INSTALL} -r "${RPM_SOURCE_DIR}/packaging/mgmtworker/requirements.txt"
%{PIP_INSTALL} --upgrade "${RPM_SOURCE_DIR}/plugins/riemann-controller"
%{PIP_INSTALL} --upgrade "${RPM_SOURCE_DIR}/workflows"


# Install stubs of cloudify packages that were merged into cloudify-common
STUBS=${RPM_SOURCE_DIR}/packaging/mgmtworker/stub_packages
%{PIP_INSTALL} --upgrade ${STUBS}/cloudify-rest-client/
%{PIP_INSTALL} --upgrade ${STUBS}/cloudify-plugins-common/
%{PIP_INSTALL} --upgrade ${STUBS}/cloudify-dsl-parser/
%{PIP_INSTALL} --upgrade ${STUBS}/cloudify-script-plugin/

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
