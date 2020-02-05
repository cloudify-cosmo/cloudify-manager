%define _agents_dir /opt/manager/resources/packages/agents

# disable inspecting the files, because it's slow and gets us nothing
%define __find_provides %{nil}
%define __find_requires %{nil}
%define _use_internal_dependency_generator 0
%define _source_payload w0.gzdio
%define _binary_payload w0.gzdio

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

BuildRequires:  python >= 2.7
Requires(pre):  shadow-utils

Source0:        http://cloudify-release-eu.s3.amazonaws.com/cloudify/5.0.5/ga-release/Ubuntu-trusty-agent_5.0.5-ga.tar.gz
Source1:        http://cloudify-release-eu.s3.amazonaws.com/cloudify/5.0.5/ga-release/Ubuntu-xenial-agent_5.0.5-ga.tar.gz
Source2:        http://cloudify-release-eu.s3.amazonaws.com/cloudify/5.0.5/ga-release/Ubuntu-bionic-agent_5.0.5-ga.tar.gz
Source3:        http://cloudify-release-eu.s3.amazonaws.com/cloudify/5.0.5/ga-release/centos-Core-agent_5.0.5-ga.tar.gz
Source4:        http://cloudify-release-eu.s3.amazonaws.com/cloudify/5.0.5/ga-release/centos-Final-agent_5.0.5-ga.tar.gz
Source5:        http://cloudify-release-eu.s3.amazonaws.com/cloudify/5.0.5/ga-release/redhat-Maipo-agent_5.0.5-ga.tar.gz
Source6:        http://cloudify-release-eu.s3.amazonaws.com/cloudify/5.0.5/ga-release/redhat-Santiago-agent_5.0.5-ga.tar.gz
Source7:        http://cloudify-release-eu.s3.amazonaws.com/cloudify/5.0.5/ga-release/cloudify-windows-agent_5.0.5-ga.exe

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
%_agents_dir
