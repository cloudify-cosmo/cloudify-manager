%define __python /opt/mgmtworker/env/bin/python
%define __jar_repack %{nil}
%define PIP_INSTALL /opt/mgmtworker/env/bin/pip install -c "${RPM_SOURCE_DIR}/packaging/mgmtworker/constraints.txt"

# Prevent mangling shebangs (RH8 build default), which fails
#  with the test files of networkx<2 due to RH8 not having python2.
%if "%{dist}" != ".el7"
%undefine __brp_mangle_shebangs
# Prevent creation of the build ids in /usr/lib, so we can still keep our RPM
#  separate from the official RH supplied software (due to a change in RH8)
%define _build_id_links none
%endif

Name:           cloudify-management-worker
Version:        %{CLOUDIFY_VERSION}
Release:        %{CLOUDIFY_PACKAGE_RELEASE}%{?dist}
Summary:        Cloudify's Management Worker
Group:          Applications/Multimedia
License:        Apache 2.0
URL:            https://github.com/cloudify-cosmo/cloudify-manager
Vendor:         Cloudify Platform Ltd.
Packager:       Cloudify Platform Ltd.

BuildRequires:  python3 >= 3.10, openssl-devel, git
BuildRequires:  postgresql-devel
BuildRequires: python3-devel
Requires:       python3 >= 3.10, postgresql-libs
Requires(pre):  shadow-utils

%description
Cloudify's Management worker


%build
python3 -m venv /opt/mgmtworker/env
%{PIP_INSTALL} --upgrade pip"<20.0" "setuptools<58.5"
%{PIP_INSTALL} -r "${RPM_SOURCE_DIR}/packaging/mgmtworker/requirements.txt"
%{PIP_INSTALL} --upgrade "${RPM_SOURCE_DIR}/mgmtworker"
%{PIP_INSTALL} --upgrade "${RPM_SOURCE_DIR}/workflows"
%{PIP_INSTALL} --upgrade "${RPM_SOURCE_DIR}/cloudify_types"

%{PIP_INSTALL} --upgrade kerberos==1.3.0


%install
mkdir -p %{buildroot}/opt/mgmtworker
mv /opt/mgmtworker/env %{buildroot}/opt/mgmtworker
mkdir -p %{buildroot}/var/log/cloudify/mgmtworker
mkdir -p %{buildroot}/opt/mgmtworker/config
mkdir -p %{buildroot}/opt/mgmtworker/work
mkdir -p %{buildroot}/opt/mgmtworker/env/plugins
mkdir -p %{buildroot}/opt/mgmtworker/env/source_plugins

cp -R ${RPM_SOURCE_DIR}/packaging/mgmtworker/files/* %{buildroot}


%pre
groupadd -fr cfyuser
getent passwd cfyuser >/dev/null || useradd -r -g cfyuser -d /etc/cloudify -s /sbin/nologin cfyuser
groupadd -fr cfylogs


%files
%defattr(-,root,root)
/etc/cloudify/logging.conf
/etc/logrotate.d/cloudify-mgmtworker
/usr/lib/systemd/system/cloudify-mgmtworker.service
%attr(750,cfyuser,cfyuser) /opt/mgmtworker/scripts/fetch-logs
%attr(750,cfyuser,cfyuser) /opt/mgmtworker/config
%attr(750,cfyuser,cfyuser) /opt/mgmtworker/work
%attr(750,cfyuser,cfyuser) /opt/mgmtworker/env/plugins
%attr(750,cfyuser,cfyuser) /opt/mgmtworker/env/source_plugins
/opt/mgmtworker
%attr(750,cfyuser,cfylogs) /var/log/cloudify/mgmtworker
