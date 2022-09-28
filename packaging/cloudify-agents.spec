%define _agents_dir /opt/manager/resources/packages/agents

# disable inspecting the files, because it's slow and gets us nothing
%define __find_provides %{nil}
%define __find_requires %{nil}
%define _use_internal_dependency_generator 0
%define _source_payload w0.gzdio
%define _binary_payload w0.gzdio

# Prevent mangling shebangs (RH8 build default), which fails
#  with the test files of networkx<2 due to RH8 not having python2.
%if "%{dist}" != ".el7"
%undefine __brp_mangle_shebangs
# Prevent creation of the build ids in /usr/lib, so we can still keep our RPM
#  separate from the official RH supplied software (due to a change in RH8)
%define _build_id_links none
%endif

Name:           cloudify-agents
Version:        %{CLOUDIFY_VERSION}
Release:        %{CLOUDIFY_PACKAGE_RELEASE}%{?dist}
BuildArch:      noarch
Summary:        Cloudify's agents bundle
Group:          Applications/Multimedia
License:        Apache 2.0
URL:            https://github.com/cloudify-cosmo/cloudify-agent
Vendor:         Cloudify Platform Ltd.
Packager:       Cloudify Platform Ltd.

Requires(pre):  shadow-utils
Requires:       python3 >= 3.6

Source0:        https://cloudify-release-eu.s3.amazonaws.com/cloudify/%{CLOUDIFY_VERSION}/%{CLOUDIFY_PACKAGE_RELEASE}-release/manylinux-x86_64-agent_%{CLOUDIFY_VERSION}-%{CLOUDIFY_PACKAGE_RELEASE}.tar.gz
Source1:        https://cloudify-release-eu.s3.amazonaws.com/cloudify/%{CLOUDIFY_VERSION}/%{CLOUDIFY_PACKAGE_RELEASE}-release/manylinux-aarch64-agent_%{CLOUDIFY_VERSION}-%{CLOUDIFY_PACKAGE_RELEASE}.tar.gz
Source2:        https://cloudify-release-eu.s3.amazonaws.com/cloudify/%{CLOUDIFY_VERSION}/%{CLOUDIFY_PACKAGE_RELEASE}-release/cloudify-windows-agent_%{CLOUDIFY_VERSION}-%{CLOUDIFY_PACKAGE_RELEASE}.exe

%description
Cloudify Agent packages


# The list of Sources above is the default set of agents.
# They will be fetched by build_rpm.py during the package
# build. If you want to use an agent package with changes
# you can place a matching named file in cloudify-manager
# (../ from here). Any extra agent packages found in that
# directory will also be packaged (files with .tar.gz and
# .exe extensions).

%install

mkdir -p %{buildroot}%_agents_dir
python3 ${RPM_SOURCE_DIR}/packaging/agents/copy_packages.py "${RPM_SOURCE_DIR}" "%{buildroot}%_agents_dir"


%pre
groupadd -fr cfyuser
getent passwd cfyuser >/dev/null || useradd -r -g cfyuser -d /etc/cloudify -s /sbin/nologin cfyuser


%files
%defattr(644,cfyuser,cfyuser,775)
%_agents_dir/*
