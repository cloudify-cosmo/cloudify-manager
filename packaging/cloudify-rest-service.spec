%define dbus_glib_version 0.100
%define dbus_version 1.6

%global __requires_exclude LIBDBUS_1_3

Name:           cloudify-rest-service
Version:        %{CLOUDIFY_VERSION}
Release:        %{CLOUDIFY_PACKAGE_RELEASE}%{?dist}
Summary:        Cloudify's REST Service
Group:          Applications/Multimedia
License:        Apache 2.0
URL:            https://github.com/cloudify-cosmo/cloudify-manager
Vendor:         Cloudify Platform Ltd.
Packager:       Cloudify Platform Ltd.

BuildRequires:  python >= 2.7, python-virtualenv
BuildRequires:  openssl-devel, openldap-devel, libffi-devel, postgresql-devel
BuildRequires:  git, sudo
BuildRequires: dbus-devel >= %{dbus_version}
BuildRequires: dbus-glib-devel >= %{dbus_glib_version}
BuildRequires: python-devel

Requires:       python >= 2.7, postgresql-libs, nginx >= 1.12, sudo, dbus >= 1.6
Requires(pre):  shadow-utils

%define _diamond_version 1.3.14
Source0:  http://www.getcloudify.org/spec/diamond-plugin/1.3.14/plugin.yaml


%description
Cloudify's REST Service.


%build

virtualenv /opt/manager/env

export REST_SERVICE_BUILD=True  # TODO: remove this hack from setup.py

/opt/manager/env/bin/pip install --upgrade pip setuptools
/opt/manager/env/bin/pip install -r "${RPM_SOURCE_DIR}/rest-service/dev-requirements.txt"
/opt/manager/env/bin/pip install "${RPM_SOURCE_DIR}/rest-service"[dbus]
/opt/manager/env/bin/pip install "${RPM_SOURCE_DIR}/amqp-postgres"

# Jinja2 includes 2 files which will only be imported if async is available,
# but rpmbuild's brp-python-bytecompile falls over when it finds them. Here
# we remove them.
rm -f /opt/manager/env/lib/python2.7/site-packages/jinja2/async*.py


%install

mkdir -p %{buildroot}/opt/manager
mv /opt/manager/env %{buildroot}/opt/manager

mkdir -p %{buildroot}/opt/manager/resources/
cp -R "${RPM_SOURCE_DIR}/resources/rest-service/cloudify/" "%{buildroot}/opt/manager/resources/"

# Create the log dirs
mkdir -p %{buildroot}/var/log/cloudify/rest
mkdir -p %{buildroot}/var/log/cloudify/amqp-postgres

# Copy static files into place. In order to have files in /packaging/files
# actually included in the RPM, they must have an entry in the %files
# section of this spec file.
cp -R ${RPM_SOURCE_DIR}/packaging/rest-service/files/* %{buildroot}

# AMQP Postgres files go in here as well, as there's no separate RPM for it
cp -R ${RPM_SOURCE_DIR}/packaging/amqp-postgres/files/* %{buildroot}

visudo -cf %{buildroot}/etc/sudoers.d/cloudify-restservice


# Install local copies of specs for URL resolver
specs="%{buildroot}/opt/manager/resources/spec"
types_yaml="${specs}/cloudify/4.5/types.yaml"
mkdir -p $(dirname "$types_yaml")
cp "${RPM_SOURCE_DIR}/resources/rest-service/cloudify/types/types.yaml" "$types_yaml"

diamond_yaml="${specs}/diamond-plugin/%{_diamond_version}/plugin.yaml"
mkdir -p $(dirname "$diamond_yaml")
cp "%{S:0}" "$diamond_yaml"


%pre

groupadd -fr cfyuser
getent passwd cfyuser >/dev/null || useradd -r -g cfyuser -d /etc/cloudify -s /sbin/nologin cfyuser


%files

/opt/manager
/etc/cloudify/delete_logs_and_events_from_db.py*
/etc/logrotate.d/cloudify-amqp-postgres
/etc/sudoers.d/cloudify-restservice
/opt/restservice
/opt/manager/scripts/set-manager-ssl.py*
/usr/lib/systemd/system/cloudify-restservice.service
/usr/lib/systemd/system/cloudify-amqp-postgres.service

%attr(750,cfyuser,adm) /var/log/cloudify/rest
%attr(750,cfyuser,adm) /var/log/cloudify/amqp-postgres
