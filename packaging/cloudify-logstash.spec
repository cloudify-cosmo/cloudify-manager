
Name:           cloudify-logstash
Version:        %{CLOUDIFY_VERSION}
Release:        %{CLOUDIFY_PACKAGE_RELEASE}%{?dist}
Summary:        Cloudify's Logstash
Group:          Applications/Multimedia
License:        Apache 2.0
URL:            https://github.com/cloudify-cosmo/cloudify-amqp-influxdb
Vendor:         Cloudify Platform Ltd.
Packager:       Cloudify Platform Ltd.

BuildRequires:  jre, rsync, logstash = 1.5.0
Requires:       jre, postgresql94-jdbc
Conflicts:      logstash

Source0:        http://repository.cloudifysource.org/cloudify/components/logstash-output-jdbc-0.2.10.gem
Source1:        http://repository.cloudifysource.org/cloudify/components/logstash-filter-json_encode-0.1.5.gem

%define _user logstash

# Work around lurking stale hashbangs from logstash's build process
%define __requires_exclude ^/home/jenkins/.*


%description
Cloudify's logstash plugins and configuration


%install

/opt/logstash/bin/plugin install ${RPM_SOURCE_DIR}/*.gem


# Copy entire logstash install
mkdir %{buildroot}/opt
cp -R /opt/logstash %{buildroot}/opt/logstash

# move & edit init script
mkdir -p %{buildroot}/etc/init.d
cp /etc/init.d/logstash %{buildroot}/etc/init.d
sed -i 's:sysconfig/\$name:sysconfig/cloudify-$name:g' %{buildroot}/etc/init.d/logstash

# Create the log dir
mkdir -p %{buildroot}/var/log/cloudify/%_user

# Create var dir
mkdir -p %{buildroot}/var/lib/logstash

# Copy static files into place. In order to have files in /packaging/files
# actually included in the RPM, they must have an entry in the %files
# section of this spec file.
cp -R ${RPM_SOURCE_DIR}/packaging/logstash/files/* %{buildroot}


%pre

# create logstash group
if ! getent group logstash >/dev/null; then
  groupadd -r logstash
fi

# create logstash user
if ! getent passwd logstash >/dev/null; then
  useradd -r -g logstash -d /opt/logstash \
    -s /sbin/nologin -c "logstash" logstash
fi


%post
/sbin/chkconfig --add logstash


%preun
if [ $1 -eq 0 ]; then
  /sbin/service logstash stop >/dev/null 2>&1 || true
  /sbin/chkconfig --del logstash
  if getent passwd logstash >/dev/null ; then
    userdel logstash
  fi

  if getent group logstash > /dev/null ; then
    groupdel logstash
  fi
fi


%files

/etc/init.d/logstash
/etc/logrotate.d/cloudify-logstash
/etc/sysconfig/cloudify-logstash

%attr(-,%_user,%_user) /opt/logstash
/opt/logstash_NOTICE.txt

/usr/lib/systemd/system/logstash.service.d/restart.conf

%attr(-,%_user,%_user) /var/lib/logstash
%attr(750,%_user,adm) /var/log/cloudify/%_user
