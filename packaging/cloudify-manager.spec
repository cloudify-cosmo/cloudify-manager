
Name:           cloudify-manager
Version:        %{CLOUDIFY_VERSION}
Release:        %{CLOUDIFY_PACKAGE_RELEASE}%{?dist}
Summary:        Cloudify's REST Service
Group:          Applications/Multimedia
License:        Apache 2.0
URL:            https://github.com/cloudify-cosmo/cloudify-manager
Vendor:         Cloudify Inc.
Packager:       Cloudify Inc.

Requires:       postgresql-server
Requires:       cloudify-agents = %{version}
Requires:       cloudify-amqp-influx = %{version}
Requires:       cloudify-logstash = %{version}
Requires:       cloudify-manager-common = %{version}
Requires:       cloudify-management-worker = %{version}
Requires:       cloudify-rest-service = %{version}
Requires:       cloudify-riemann = %{version}
Requires:       cloudify-stage = %{version}


%description
cloudify-manager full install.


%files
