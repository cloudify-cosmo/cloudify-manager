%define _manager_env /opt/manager/env
%define __python %_manager_env/bin/python

%define dbus_glib_version 0.100
%define dbus_version 1.6
%define __jar_repack %{nil}
%global __requires_exclude LIBDBUS_1_3

# Prevent mangling shebangs (RH8 build default), which fails
#  with the test files of networkx<2 due to RH8 not having python2.
%if "%{dist}" != ".el7"
%undefine __brp_mangle_shebangs
# Prevent creation of the build ids in /usr/lib, so we can still keep our RPM
#  separate from the official RH supplied software (due to a change in RH8)
%define _build_id_links none
%endif

Name:           cloudify-rest-service
Version:        %{CLOUDIFY_VERSION}
Release:        %{CLOUDIFY_PACKAGE_RELEASE}%{?dist}
Summary:        Cloudify's REST Service
Group:          Applications/Multimedia
License:        Apache 2.0
URL:            https://github.com/cloudify-cosmo/cloudify-manager
Vendor:         Cloudify Platform Ltd.
Packager:       Cloudify Platform Ltd.

BuildRequires:  python3 >= 3.6
BuildRequires:  openssl-devel, openldap-devel, libffi-devel, postgresql-devel
BuildRequires:  git, sudo
BuildRequires: dbus-devel >= %{dbus_version}
BuildRequires: dbus-glib-devel >= %{dbus_glib_version}
BuildRequires: python3-devel

Requires:       python3 >= 3.6, postgresql-libs, sudo, dbus >= 1.6, nginx
Requires(pre):  shadow-utils

%description
Cloudify's REST Service.


%build

python3 -m venv %_manager_env

%_manager_env/bin/pip install --upgrade pip"<20.0" setuptools
%_manager_env/bin/pip install -r "${RPM_SOURCE_DIR}/rest-service/requirements.txt"
%_manager_env/bin/pip install -r "${RPM_SOURCE_DIR}/api-service/requirements.txt"
%_manager_env/bin/pip install "${RPM_SOURCE_DIR}/rest-service"[dbus]
%_manager_env/bin/pip install "${RPM_SOURCE_DIR}/api-service"
%_manager_env/bin/pip install "${RPM_SOURCE_DIR}/amqp-postgres"
%_manager_env/bin/pip install "${RPM_SOURCE_DIR}/execution-scheduler"


%install

mkdir -p %{buildroot}/opt/manager
mv %_manager_env %{buildroot}/opt/manager

mkdir -p %{buildroot}/opt/manager/resources/
cp -R "${RPM_SOURCE_DIR}/resources/rest-service/cloudify/" "%{buildroot}/opt/manager/resources/"

# Create the log dirs
mkdir -p %{buildroot}/var/log/cloudify/rest
mkdir -p %{buildroot}/var/log/cloudify/amqp-postgres
mkdir -p %{buildroot}/var/log/cloudify/execution-scheduler

# Dir for snapshot restore marker files (CY-1821)
mkdir -p %{buildroot}/opt/manager/snapshot_status

# Copy static files into place. In order to have files in /packaging/files
# actually included in the RPM, they must have an entry in the %files
# section of this spec file.
cp -R ${RPM_SOURCE_DIR}/packaging/rest-service/files/* %{buildroot}

# AMQP Postgres and execution scheduler files go in here as well, as there are no separate RPMs for them
cp -R ${RPM_SOURCE_DIR}/packaging/amqp-postgres/files/* %{buildroot}
cp -R ${RPM_SOURCE_DIR}/packaging/execution-scheduler/files/* %{buildroot}

visudo -cf %{buildroot}/etc/sudoers.d/cloudify-restservice

# Install local copies of types for URL resolver
specs="%{buildroot}/opt/manager/resources/spec/cloudify"
types_yaml="${specs}/6.4.0/types.yaml"
mkdir -p $(dirname "$types_yaml")
cp "${RPM_SOURCE_DIR}/resources/rest-service/cloudify/types/types.yaml" "$types_yaml"
cache_root="${RPM_SOURCE_DIR}/resources/rest-service/cloudify/types/cache"
# This would be better as a glob, but then we end up fighting rpm build
for ver in ${cache_root}/*; do
    cp -r "${ver}" "${specs}"
done


%pre

groupadd -fr cfyuser
getent passwd cfyuser >/dev/null || useradd -r -g cfyuser -d /etc/cloudify -s /sbin/nologin cfyuser
usermod -aG cfyuser nginx
groupadd -fr cfylogs

%post
if [ $1 -gt 1 ]; then
    touch "%{_localstatedir}/lib/rpm-state/cloudify-upgraded"
fi
exit 0

%posttrans
if [ -f "%{_localstatedir}/lib/rpm-state/cloudify-upgraded" ]; then
    rm "%{_localstatedir}/lib/rpm-state/cloudify-upgraded"

    chmod 440 /etc/cloudify/ssl/*stage_db.key || true
    chmod 440 /etc/cloudify/ssl/*composer_db.key || true

    if [ -e "/var/run/supervisord.sock" ]; then
        if [ -e "/etc/supervisord.d/haproxy.conf" ]; then
            supervisorctl stop haproxy && supervisorctl remove haproxy
        fi
        supervisorctl stop cloudify-restservice
        supervisorctl stop cloudify-api
        supervisorctl stop cloudify-execution-scheduler
        supervisorctl stop cloudify-amqp-postgres
    else
        if systemctl is-enabled haproxy 2>/dev/null; then
            systemctl stop haproxy && systemctl disable haproxy
        fi
        systemctl stop cloudify-restservice
        systemctl stop cloudify-api
        systemctl stop cloudify-execution-scheduler
        systemctl stop cloudify-amqp-postgres
    fi

    export MANAGER_REST_CONFIG_PATH=/opt/manager/cloudify-rest.conf

    /opt/manager/env/bin/python -m manager_rest.update_rest_db_config --commit
    pushd /opt/manager/resources/cloudify/migrations
        /opt/manager/env/bin/alembic upgrade head
        CURRENT_DB=$(/opt/manager/env/bin/alembic current)
    popd
    /opt/manager/env/bin/python -m manager_rest.update_managers_version %{CLOUDIFY_VERSION}
    chown cfyuser: /opt/manager/resources

    if [ -e "/var/run/supervisord.sock" ]; then
        supervisorctl start cloudify-restservice
        supervisorctl start cloudify-api
        supervisorctl start cloudify-execution-scheduler
        supervisorctl start cloudify-amqp-postgres
    else
        systemctl start cloudify-restservice
        systemctl start cloudify-api
        systemctl start cloudify-execution-scheduler
        systemctl start cloudify-amqp-postgres
    fi

    echo "
#############################################################

Congratulations on upgrading Cloudify to %{CLOUDIFY_VERSION}!

Update notes:
 * Clustered DB no longer requires HAProxy. The config files at /opt/manager/cloudify-rest.conf,
   /opt/cloudify-stage/conf/app.json and /opt/cloudify-composer/backend/conf/prod.json
   have been updated. You can view them to confirm they contain the correct DB endpoint(s).
 * The database schema has been updated. Current database schema revision: ${CURRENT_DB}

#############################################################
"
fi
exit 0


%files

%attr(750,cfyuser,cfyuser)  /opt/manager
/etc/cloudify/delete_logs_and_events_from_db.py*
%dir /opt/cloudify/encryption
/opt/cloudify/encryption/update-encryption-key
/etc/logrotate.d/cloudify-amqp-postgres
/etc/logrotate.d/cloudify-execution-scheduler
/etc/sudoers.d/cloudify-restservice
/opt/restservice
/usr/lib/systemd/system/cloudify-restservice.service
/usr/lib/systemd/system/cloudify-api.service
/usr/lib/systemd/system/cloudify-amqp-postgres.service
/usr/lib/systemd/system/cloudify-execution-scheduler.service

/opt/manager/scripts/load_permissions.py
/opt/manager/scripts/create_system_filters.py
/opt/manager/snapshot_status
%attr(750,cfyuser,cfylogs) /var/log/cloudify/rest
%attr(750,cfyuser,cfylogs) /var/log/cloudify/amqp-postgres
%attr(750,cfyuser,cfylogs) /var/log/cloudify/execution-scheduler
%attr(550,root,cfyuser) /opt/cloudify/encryption/update-encryption-key
