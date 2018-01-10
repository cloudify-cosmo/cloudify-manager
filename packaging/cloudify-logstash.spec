
Name:           cloudify-logstash
Version:        %{CLOUDIFY_VERSION}
Release:        %{CLOUDIFY_PACKAGE_RELEASE}%{?dist}
Summary:        Cloudify's Logstash
Group:          Applications/Multimedia
License:        Apache 2.0
URL:            https://github.com/cloudify-cosmo/cloudify-amqp-influxdb
Vendor:         Cloudify Platform Ltd.
Packager:       Cloudify Platform Ltd.

BuildRequires:  jre, rsync
Requires:       logstash, jre, postgresql-jdbc

Source0:        http://repository.cloudifysource.org/cloudify/components/logstash-output-jdbc-0.2.10.gem
Source1:        http://repository.cloudifysource.org/cloudify/components/logstash-filter-json_encode-0.1.5.gem

%define _user logstash


%description
Cloudify's logstash plugins and configuration


%prep

mkdir -p %{buildroot}/opt/logstash
# cloudify-premium needs to be installed in to the restservice virtualenv,
# but the rest of the files there belong to a different package. We shall
# copy the existing env so that we can compare any changes once the new python packages are installed.
cp -r /opt/logstash /tmp/existing_env


%build

/opt/logstash/bin/plugin install ${RPM_SOURCE_DIR}/*.gem


%install

mkdir -p %{buildroot}/opt/logstash
# Now we copy the files into the buildroot, checking against existing_env
# so that only new files will be included in the RPM.
rsync -rlc --compare-dest /tmp/existing_env /opt/logstash/vendor %{buildroot}/opt/logstash

# Clear out empty dirs from the result
find %{buildroot} -depth -type d -empty -delete

# Create the log dir
mkdir -p %{buildroot}/var/log/cloudify/%_user

# Copy static files into place. In order to have files in /packaging/files
# actually included in the RPM, they must have an entry in the %files
# section of this spec file.
cp -R ${RPM_SOURCE_DIR}/packaging/logstash/files/* %{buildroot}


%files

/etc/logrotate.d/cloudify-logstash
%attr(750,%_user,adm) /var/log/cloudify/%_user
%attr(-,%_user,%_user) /opt/logstash/vendor/local_gems
