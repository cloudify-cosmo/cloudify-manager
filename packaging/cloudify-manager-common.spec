
Name:           cloudify-manager-common
Version:        %{CLOUDIFY_VERSION}
Release:        %{CLOUDIFY_PACKAGE_RELEASE}%{?dist}
Summary:        Cloudify's Logstash
Group:          Applications/Multimedia
License:        Apache 2.0
URL:            https://github.com/cloudify-cosmo/cloudify-manager
Vendor:         Gigaspaces Inc.
Packager:       Gigaspaces Inc.

BuildRequires:  python, python-setuptools
Requires:       python, python-setuptools, PyYAML, python-jinja2, python2-argh = 0.26.1


%define _name cfy-manager


%description
Cloudify common components

-`cfy_manager` helper script


%prep

# %setup -n %{name}-%{unmangled_version} -n %{name}-%{unmangled_version}


%build

# python setup.py build


%install

cd ${RPM_SOURCE_DIR}/cfy-manager
python setup.py install --single-version-externally-managed -O1 --root=$RPM_BUILD_ROOT --record=${RPM_BUILD_DIR}/INSTALLED_FILES


%pre
%post
%preun
%postun


%files

%files -f INSTALLED_FILES
