%define dbus_glib_version 0.70
%define dbus_version 0.90

Name:           cloudify-rest-service
Version:        %{CLOUDIFY_VERSION}
Release:        %{CLOUDIFY_PACKAGE_RELEASE}%{?dist}
Summary:        Cloudify's REST Service
Group:          Applications/Multimedia
License:        Apache 2.0
URL:            https://github.com/cloudify-cosmo/cloudify-manager
Vendor:         Gigaspaces Inc.
Packager:       Gigaspaces Inc.

BuildRequires:  python >= 2.7, python-virtualenv
BuildRequires:  openssl-devel, postgresql-devel, openldap-devel, libffi-devel
BuildRequires:  git, sudo
BuildRequires: dbus-devel >= %{dbus_version}
BuildRequires: dbus-glib-devel >= %{dbus_glib_version}
BuildRequires: python-devel

Requires:       python >= 2.7, postgresql-libs, nginx >= 1.12, sudo
Requires(pre):  shadow-utils



%description
Cloudify's REST Service.


%build

virtualenv /opt/manager/env

export REST_SERVICE_BUILD=True  # TODO: remove this hack from setup.py

/opt/manager/env/bin/pip install --upgrade pip setuptools
/opt/manager/env/bin/pip install \
    'git+https://github.com/cloudify-cosmo/cloudify-dsl-parser#egg=cloudify-dsl-parser==4.3.dev1' \
    https://github.com/cloudify-cosmo/incubator-ariatosca/archive/master.tar.gz \
    "${RPM_SOURCE_DIR}/rest-service"[dbus]

# Jinja2 includes 2 files which will only be imported if async is available,
# but rpmbuild's brp-python-bytecompile falls over when it finds them. Here
# we remove them.
rm /opt/manager/env/lib/python2.7/site-packages/jinja2/async*.py


%install

mkdir -p %{buildroot}/opt/manager
mv /opt/manager/env %{buildroot}/opt/manager

mkdir -p %{buildroot}/opt/manager/resources/
cp -R "${RPM_SOURCE_DIR}/resources/rest-service/cloudify/" "%{buildroot}/opt/manager/resources/"

# Create the log dir
mkdir -p %{buildroot}/var/log/cloudify/rest

# Copy static files into place. In order to have files in /packaging/files
# actually included in the RPM, they must have an entry in the %files
# section of this spec file.
cp -R ${RPM_SOURCE_DIR}/packaging/rest-service/files/* %{buildroot}

visudo -cf %{buildroot}/etc/sudoers.d/cloudify-restservice


%pre

groupadd -fr cfyuser
getent passwd cfyuser >/dev/null || useradd -r -g cfyuser -d /etc/cloudify -s /sbin/nologin cfyuser


%files

/opt/manager

/etc/sudoers.d/cloudify-restservice
/etc/cloudify/delete_logs_and_events_from_db.py*
/opt/restservice/NOTICE.txt
/opt/restservice/set-manager-ssl.py*
/usr/lib/systemd/system/cloudify-rest-service.service

%attr(750,cfyuser,adm) /var/log/cloudify/rest
