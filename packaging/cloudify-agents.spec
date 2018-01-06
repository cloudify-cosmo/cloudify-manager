%define _agents_dir /opt/manager/resources/packages/agents

Name:           cloudify-agents
Version:        %{CLOUDIFY_VERSION}
Release:        %{CLOUDIFY_PACKAGE_RELEASE}%{?dist}
Summary:        Cloudify's agents bundle
Group:          Applications/Multimedia
License:        Apache 2.0
URL:            https://github.com/cloudify-cosmo/cloudify-agent
Vendor:         Cloudify Platform Ltd.
Packager:       Cloudify Platform Ltd.

BuildRequires:  python >= 2.7
Requires(pre):  shadow-utils


%description
Cloudify Agent packages


%prep
curl https://raw.githubusercontent.com/cloudify-cosmo/cloudify-versions/master/packages-urls/agent-packages.yaml > /tmp/agents-list.txt


%build
mkdir -p %_agents_dir
pushd %_agents_dir
    xargs -I url curl -O url </tmp/agents-list.txt
    python %{RPM_SOURCE_DIR}/packaging/agents/rename_packages.py .
popd
rm /tmp/agents-list.txt


%install
mkdir -p %{buildroot}/opt
mv /opt/manager %{buildroot}/opt/manager


%pre
groupadd -fr cfyuser
getent passwd cfyuser >/dev/null || useradd -r -g cfyuser -d /etc/cloudify -s /sbin/nologin cfyuser


%files
%attr(750,cfyuser,adm) /opt/manager/resources/packages/agents
