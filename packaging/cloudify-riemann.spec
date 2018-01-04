%define _user riemann

Name:           cloudify-riemann
Version:        %{CLOUDIFY_VERSION}
Release:        %{CLOUDIFY_PACKAGE_RELEASE}%{?dist}
Summary:        Cloudify's Riemann configuration
Group:          Applications/Multimedia
License:        Apache 2.0
URL:            https://github.com/cloudify-cosmo/cloudify-manager
Vendor:         Gigaspaces Inc.
Packager:       Gigaspaces Inc.

Requires:       riemann, daemonize
Requires:       cloudify-rest-service

Source0:        http://repository.cloudifysource.org/cloudify/components/langohr.jar


%description
Cloudify's Riemann configuration


%install

for dir in /opt/riemann /var/log/cloudify/riemann /opt/lib /etc/riemann/conf.d
do
    mkdir -p %{buildroot}$dir
done

# Copy static files into place. In order to have files in /packaging/files
# actually included in the RPM, they must have an entry in the %files
# section of this spec file.
cp -R ${RPM_SOURCE_DIR}/packaging/riemann/files/* %{buildroot}

cp %{S:0} %{buildroot}/opt/lib


%pre

groupadd -fr %_user
getent passwd %_user >/dev/null || useradd -r -g %_user -d /etc/cloudify -s /sbin/nologin cfyuser


%files

/etc/logrotate.d/cloudify-riemann
/etc/riemann/conf.d/manager.config
/etc/riemann/main.clj
/opt/lib/langohr.jar
/opt/manager/scripts/activate_riemann_policies
/opt/riemann_NOTICE.txt
/usr/lib/systemd/system/cloudify-riemann.service

%dir %attr(770,%user,cfyuser) /opt/riemann
%dir %attr(-,%_user,adm) /var/log/cloudify/riemann
