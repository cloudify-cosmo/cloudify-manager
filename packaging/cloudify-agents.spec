%define _agents_dir /opt/manager/resources/packages/agents

# disable inspecting the files, because it's slow and gets us nothing
%define __find_provides %{nil}
%define __find_requires %{nil}
%define _use_internal_dependency_generator 0
%define _source_payload w0.gzdio
%define _binary_payload w0.gzdio

# this prevents networkx<2 failure in RH8
%if "%{dist}" != ".el7"
%undefine __brp_mangle_shebangs
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

%if "%{dist}" == ".el7"
BuildRequires:  python >= 2.7
%else
BuildRequires:  python3 >= 3.6
%endif

Requires(pre):  shadow-utils

Source0:        https://cloudify-release-eu.s3.amazonaws.com/cloudify/%{CLOUDIFY_VERSION}/%{CLOUDIFY_PACKAGE_RELEASE}-release/Ubuntu-xenial-agent_%{CLOUDIFY_VERSION}-%{CLOUDIFY_PACKAGE_RELEASE}.tar.gz
Source1:        https://cloudify-release-eu.s3.amazonaws.com/cloudify/%{CLOUDIFY_VERSION}/%{CLOUDIFY_PACKAGE_RELEASE}-release/Ubuntu-bionic-agent_%{CLOUDIFY_VERSION}-%{CLOUDIFY_PACKAGE_RELEASE}.tar.gz
Source2:        https://cloudify-release-eu.s3.amazonaws.com/cloudify/%{CLOUDIFY_VERSION}/%{CLOUDIFY_PACKAGE_RELEASE}-release/centos-8-agent_%{CLOUDIFY_VERSION}-%{CLOUDIFY_PACKAGE_RELEASE}.tar.gz
Source3:        https://cloudify-release-eu.s3.amazonaws.com/cloudify/%{CLOUDIFY_VERSION}/%{CLOUDIFY_PACKAGE_RELEASE}-release/centos-Core-agent_%{CLOUDIFY_VERSION}-%{CLOUDIFY_PACKAGE_RELEASE}.tar.gz
Source4:        https://cloudify-release-eu.s3.amazonaws.com/cloudify/%{CLOUDIFY_VERSION}/%{CLOUDIFY_PACKAGE_RELEASE}-release/redhat-Ootpa-agent_%{CLOUDIFY_VERSION}-%{CLOUDIFY_PACKAGE_RELEASE}.tar.gz
Source5:        https://cloudify-release-eu.s3.amazonaws.com/cloudify/%{CLOUDIFY_VERSION}/%{CLOUDIFY_PACKAGE_RELEASE}-release/redhat-Maipo-agent_%{CLOUDIFY_VERSION}-%{CLOUDIFY_PACKAGE_RELEASE}.tar.gz
Source6:        https://cloudify-release-eu.s3.amazonaws.com/cloudify/%{CLOUDIFY_VERSION}/%{CLOUDIFY_PACKAGE_RELEASE}-release/cloudify-windows-agent_%{CLOUDIFY_VERSION}-%{CLOUDIFY_PACKAGE_RELEASE}.exe
Source7:        https://cloudify-release-eu.s3.amazonaws.com/cloudify/%{CLOUDIFY_VERSION}/%{CLOUDIFY_PACKAGE_RELEASE}-release/centos-Altarch-agent_%{CLOUDIFY_VERSION}-%{CLOUDIFY_PACKAGE_RELEASE}.tar.gz

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
python ${RPM_SOURCE_DIR}/packaging/agents/copy_packages.py "${RPM_SOURCE_DIR}" "%{buildroot}%_agents_dir"


%pre
groupadd -fr cfyuser
getent passwd cfyuser >/dev/null || useradd -r -g cfyuser -d /etc/cloudify -s /sbin/nologin cfyuser


%files
%defattr(644,cfyuser,cfyuser,775)
%_agents_dir/*
