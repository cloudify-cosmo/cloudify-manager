
Name:           cloudify-rabbitmq
Version:        %{CLOUDIFY_VERSION}
Release:        %{CLOUDIFY_PACKAGE_RELEASE}%{?dist}
BuildArch:      noarch
Summary:        Cloudify's RabbitMQ configuration
Group:          Applications/Multimedia
License:        Apache 2.0
URL:            https://github.com/cloudify-cosmo/cloudify-amqp-influxdb
Vendor:         Cloudify Platform Ltd.
Packager:       Cloudify Platform Ltd.

Requires:       rabbitmq-server = 3.5


%define _user rabbitmq


%description
Cloudify's RabbitMQ configuration


%prep


%build


%install

mkdir -p %{buildroot}/var/log/cloudify/rabbitmq

cp -R ${RPM_SOURCE_DIR}/packaging/rabbitmq/files/* %{buildroot}


%files

/etc/logrotate.d/cloudify-rabbitmq
/etc/rabbitmq/definitions.json
/etc/rabbitmq/enabled_plugins
/etc/rabbitmq/rabbitmq-env.conf
/etc/security/limits.d/rabbitmq.conf
/usr/lib/systemd/system/cloudify-rabbitmq.service
%attr(750,%_user,adm) /var/log/cloudify/%_user
