
Name:           cloudify-logstash
Version:        %{CLOUDIFY_VERSION}
Release:        %{CLOUDIFY_PACKAGE_RELEASE}%{?dist}
Summary:        Cloudify's Logstash
Group:          Applications/Multimedia
License:        Apache 2.0
URL:            https://github.com/cloudify-cosmo/cloudify-manager
Vendor:         Cloudify Platform Ltd.
Packager:       Cloudify Platform Ltd.

BuildRequires:  jre, rsync, logstash = 1:1.5.0
Requires:       jre
Conflicts:      logstash

Source0:        http://repository.cloudifysource.org/cloudify/components/postgresql-9.4.1212.jar
Source1:        http://repository.cloudifysource.org/cloudify/components/logstash-output-jdbc-0.2.10.gem
Source2:        http://repository.cloudifysource.org/cloudify/components/logstash-filter-json_encode-0.1.5.gem

%define _user logstash

# Disable auto requirements
AutoReqProv:    no


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
# This part is to make logstash service only claim to have started when it has /really/ started
sed -i "67i\ \ done" %{buildroot}/etc/init.d/logstash
sed -i "67i\ \ \ \ sleep 2" %{buildroot}/etc/init.d/logstash
sed -i '67i\ \ \ \ echo "${name} starting (waited $(( ${attempt} * 2)) seconds)..."' %{buildroot}/etc/init.d/logstash
sed -i "67i\ \ \ \ fi" %{buildroot}/etc/init.d/logstash
sed -i "67i\ \ \ \ \ \ exit 1" %{buildroot}/etc/init.d/logstash
sed -i '67i\ \ \ \ \ \ rm ${pidfile}' %{buildroot}/etc/init.d/logstash
sed -i '67i\ \ \ \ \ \ kill -9 $(cat ${pidfile})' %{buildroot}/etc/init.d/logstash
sed -i '67i\ \ \ \ \ \ echo "${name} failed to start within 2 minutes"' %{buildroot}/etc/init.d/logstash 
sed -i '67i\ \ \ \ if [[ ${attempt} -eq 60 ]]; then' %{buildroot}/etc/init.d/logstash
sed -i '67i\ \ \ \ attempt=$(( ${attempt} + 1 ))' %{buildroot}/etc/init.d/logstash
sed -i "67i\ \ while ! ps aux | grep 'Xbootclasspath/a:/opt/logstash/vendor/jruby/lib/jruby.jar' | grep 'f /etc/logstash/conf.d' >/dev/null; do" %{buildroot}/etc/init.d/logstash
sed -i "67i\ \ attempt=-1" %{buildroot}/etc/init.d/logstash
sed -i "67i\ " %{buildroot}/etc/init.d/logstash

# Create the log dir
mkdir -p %{buildroot}/var/log/cloudify/%_user

# Create var dir
mkdir -p %{buildroot}/var/lib/logstash

# Copy postgresql-jdbc jar into place
%define _jdbc_dir %{buildroot}/opt/logstash/vendor/jar/jdbc
mkdir -p %_jdbc_dir
cp "%{S:0}" %{_jdbc_dir}/postgresql94-jdbc.jar

# Copy static files into place. In order to have files in /packaging/files
# actually included in the RPM, they must have an entry in the %files
# section of this spec file.
cp -R ${RPM_SOURCE_DIR}/packaging/logstash/files/* %{buildroot}


%pre

groupadd -fr %_user
getent passwd %_user >/dev/null || useradd -r -g %_user -d /etc/cloudify -s /sbin/nologin %_user


%files

/etc/init.d/logstash
/etc/logrotate.d/cloudify-logstash
/etc/sysconfig/cloudify-logstash

%attr(-,%_user,%_user) /opt/logstash
/opt/logstash_NOTICE.txt

/usr/lib/systemd/system/logstash.service.d

%attr(-,%_user,%_user) /var/lib/logstash
%attr(750,%_user,adm) /var/log/cloudify/%_user
