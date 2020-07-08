
Name:           cloudify-manager-ip-setter
Version:        %{CLOUDIFY_VERSION}
Release:        %{CLOUDIFY_PACKAGE_RELEASE}%{?dist}
BuildArch:      noarch
Summary:        Cloudify Manager IP Setter
Group:          Applications/Multimedia
License:        Apache 2.0
URL:            https://github.com/cloudify-cosmo/cloudify-manager
Vendor:         Cloudify Platform Ltd.
Packager:       Cloudify Platform Ltd.


%description
Utility to configure the manager IP address when bringing up a new image-based instance


%install

# Copy static files into place. In order to have files in /packaging/files
# actually included in the RPM, they must have an entry in the %files
# section of this spec file.
cp -R ${RPM_SOURCE_DIR}/packaging/ip_setter/files/* %{buildroot}


%files
/etc/sudoers.d/cloudify-manager-ip-setter
/opt/cloudify/manager-ip-setter/
