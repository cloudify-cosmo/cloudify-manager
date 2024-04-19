%define __python /opt/plugins-common-3.6/env/bin/python
%define __jar_repack %{nil}
%define __find_provides %{nil}
%define __find_requires %{nil}
%define _use_internal_dependency_generator 0

%define PIP_INSTALL /opt/plugins-common-3.6/env/bin/pip install

# Prevent mangling shebangs (RH8 build default), which fails
#  with the test files of networkx<2 due to RH8 not having python2.
%if "%{dist}" != ".el7"
%undefine __brp_mangle_shebangs
# Prevent creation of the build ids in /usr/lib, so we can still keep our RPM
#  separate from the official RH supplied software (due to a change in RH8)
%define _build_id_links none
%endif

Name:           cloudify-plugins-common-python36
Version:        %{CLOUDIFY_VERSION}
Release:        %{CLOUDIFY_PACKAGE_RELEASE}%{?dist}
Summary:        Cloudify's python3.6 common plugins
Group:          Applications/Multimedia
License:        Apache 2.0
URL:            https://github.com/cloudify-cosmo/cloudify-manager
Vendor:         Cloudify Platform Ltd.
Packager:       Cloudify Platform Ltd.

BuildRequires:  python3 >= 3.6
Requires: python3 >= 3.6

%description
Cloudify's python3.6 common plugins

%build

# Create the venv with the custom Python symlinked in
python3 -m venv /opt/plugins-common-3.6/env
%{PIP_INSTALL} --upgrade pip setuptools

%install
mkdir -p %{buildroot}/opt
mv /opt/plugins-common-3.6 %{buildroot}/opt/plugins-common-3.6

%pre
groupadd -fr cfyuser
getent passwd cfyuser >/dev/null || useradd -r -g cfyuser -d /etc/cloudify -s /sbin/nologin cfyuser
groupadd -fr cfylogs

%files

%defattr(-,root,root)
/opt/plugins-common-3.6
