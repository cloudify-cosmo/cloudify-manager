# Prevent creation of the build ids in /usr/lib, so we can still keep our RPM
# separate from the official RH supplied software (due to a change in RH8)
%if "%{dist}" != ".el7"
%define _build_id_links none
%endif

Name:           cloudify-rabbitmq
Version:        %{CLOUDIFY_VERSION}
Release:        %{CLOUDIFY_PACKAGE_RELEASE}%{?dist}
BuildArch:      noarch
Summary:        Cloudify's RabbitMQ configuration
Group:          Applications/Multimedia
License:        Apache 2.0
URL:            https://github.com/cloudify-cosmo/cloudify-manager
Vendor:         Cloudify Platform Ltd.
Packager:       Cloudify Platform Ltd.

Requires:       rabbitmq-server


%define _user rabbitmq


%description
Cloudify's RabbitMQ configuration


%prep


%build


%install

mkdir -p %{buildroot}/var/log/cloudify/rabbitmq

cp -R ${RPM_SOURCE_DIR}/packaging/rabbitmq/files/* %{buildroot}


%pre
groupadd -fr cfylogs


%files

%config /etc/logrotate.d/cloudify-rabbitmq
%config /etc/cloudify/rabbitmq/definitions.json
%config /etc/cloudify/rabbitmq/enabled_plugins
%config /etc/cloudify/rabbitmq/rabbitmq.config
%config /etc/security/limits.d/rabbitmq.conf
/opt/rabbitmq_NOTICE.txt
/usr/lib/systemd/system/cloudify-rabbitmq.service
%attr(750,%_user,cfylogs) /var/log/cloudify/%_user
