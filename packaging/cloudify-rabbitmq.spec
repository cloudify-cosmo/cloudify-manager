
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

Requires:       rabbitmq-server = 3.7.7


%define _user cfyuser


%description
Cloudify's RabbitMQ configuration


%prep


%build


%install

mkdir -p %{buildroot}/var/log/cloudify/rabbitmq

cp -R ${RPM_SOURCE_DIR}/packaging/rabbitmq/files/* %{buildroot}


%files

%attr(750,cfyuser,cfyuser) /etc/logrotate.d/cloudify-rabbitmq
%attr(750,cfyuser,cfyuser) /etc/cloudify/rabbitmq/definitions.json
%attr(750,cfyuser,cfyuser) /etc/cloudify/rabbitmq/enabled_plugins
%attr(750,cfyuser,cfyuser) /etc/cloudify/rabbitmq/rabbitmq.config
%attr(750,cfyuser,cfyuser) /etc/security/limits.d/rabbitmq.conf
%attr(750,cfyuser,cfyuser) /opt/rabbitmq_NOTICE.txt
%attr(750,cfyuser,cfyuser) /usr/lib/systemd/system/cloudify-rabbitmq.service
%attr(750,%_user,adm) /var/log/cloudify/rabbitmq
