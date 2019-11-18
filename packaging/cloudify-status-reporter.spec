%define _status_reporter_env /opt/status-reporter/env

Name:           cloudify-status-reporter
Version:        %{CLOUDIFY_VERSION}
Release:        %{CLOUDIFY_PACKAGE_RELEASE}%{?dist}
Summary:        Cloudify Status Reporter
Group:          Applications/Multimedia
License:        Apache 2.0
URL:            https://github.com/cloudify-cosmo/cloudify-manager
Vendor:         Cloudify Platform Ltd.
Packager:       Cloudify Platform Ltd.

BuildRequires:  python >= 2.7, python-virtualenv
Requires:       python >= 2.7

%description
Service for reporting the status of every Cloudify component

%build

virtualenv %_status_reporter_env

%_status_reporter_env/bin/pip install --upgrade pip setuptools
%_status_reporter_env/bin/pip install -r "${RPM_SOURCE_DIR}/packaging/status-reporter/requirements.txt"
%_status_reporter_env/bin/pip install "${RPM_SOURCE_DIR}/status-reporter"

%install

mkdir -p %{buildroot}/opt/status-reporter
mv %_status_reporter_env %{buildroot}/opt/status-reporter

# Create the log dirs
mkdir -p %{buildroot}/var/log/cloudify/status-reporter

# Copy static files into place. In order to have files in /packaging/files
# actually included in the RPM, they must have an entry in the %files
# section of this spec file.
cp -R ${RPM_SOURCE_DIR}/packaging/status-reporter/files/* %{buildroot}

%pre

getent passwd cfyreporter >/dev/null || useradd -r -d /etc/cloudify -s /sbin/nologin cfyreporter

%files
/etc/logrotate.d/cloudify-status-reporter
%attr(750,cfyreporter,adm) /opt/status-reporter
%attr(750,cfyreporter,adm) /var/log/cloudify/status-reporter
