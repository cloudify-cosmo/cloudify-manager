%define __python /opt/mgmtworker/env/bin/python
%define __jar_repack %{nil}
%define PIP_INSTALL /opt/mgmtworker/env/bin/pip install
%define __find_provides %{nil}
%define __find_requires %{nil}
%define _use_internal_dependency_generator 0

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

BuildRequires:  openssl-devel, git
BuildRequires:  postgresql-devel
Requires:       postgresql-libs
Requires(pre):  shadow-utils

Requires:       python3 >= 3.6
BuildRequires:  python3 >= 3.6


Source0:        https://cloudify-cicd.s3.amazonaws.com/python-build-packages/cfy-python3.10-%{ARCHITECTURE}.tgz
Source1:        https://cloudify-cicd.s3.amazonaws.com/python-build-packages/cfy-python3.11-%{ARCHITECTURE}.tgz

%description
Cloudify's Management worker

%prep
sudo tar xf %{S:0} -C /
sudo tar xf %{S:1} -C /

%build

# Create the venv with the custom Python symlinked in
/opt/python3.11/bin/python3.11 -m venv /opt/mgmtworker/env

%{PIP_INSTALL} --upgrade pip "setuptools<=63.2"
%{PIP_INSTALL} -r "${RPM_SOURCE_DIR}/packaging/mgmtworker/requirements.txt"
%{PIP_INSTALL} --upgrade "${RPM_SOURCE_DIR}/mgmtworker"
%{PIP_INSTALL} --upgrade "${RPM_SOURCE_DIR}/cloudify_types"

%{PIP_INSTALL} --upgrade kerberos==1.3.1

# create a python3.6 venv with common & requirements preinstalled, to be used
# as a base virtualenv for python3.6 plugins
python3.6 -m venv /opt/plugins-common-3.6
/opt/plugins-common-3.6/bin/pip install --upgrade pip "setuptools<=63.2"
/opt/plugins-common-3.6/bin/pip install -r "${RPM_SOURCE_DIR}/packaging/mgmtworker/requirements.txt"

# create a python3.10 venv with common & requirements preinstalled, to be used
# as a base virtualenv for python3.10 plugins
/opt/python3.10/bin/python3.10 -m venv /opt/plugins-common-3.10
/opt/plugins-common-3.10/bin/pip install --upgrade pip "setuptools<=63.2"
/opt/plugins-common-3.10/bin/pip install -r "${RPM_SOURCE_DIR}/packaging/mgmtworker/requirements.txt"


%install

mkdir -p %{buildroot}/opt/mgmtworker
mv /opt/mgmtworker/env %{buildroot}/opt/mgmtworker
mv /opt/plugins-common-3.6 %{buildroot}/opt/plugins-common-3.6
mv /opt/plugins-common-3.10 %{buildroot}/opt/plugins-common-3.10

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
/opt/plugins-common-3.6
/opt/plugins-common-3.10
%attr(750,cfyuser,cfylogs) /var/log/cloudify/mgmtworker
