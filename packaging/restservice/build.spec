
Name:           cloudify-rest-service
Version:        4.2
Release:        1%{?dist}
Summary:        Cloudify's REST Service
Group:          Applications/Multimedia
License:        Apache 2.0
URL:            https://github.com/cloudify-cosmo/cloudify-manager
Vendor:         Gigaspaces Inc.
Packager:       Gigaspaces Inc.

BuildRequires:  python >= 2.7, python-virtualenv, openssl-devel, postgresql-devel, openldap-devel, git
Requires:       python >= 2.7, postgresql-libs, nginx >= 1.12
Requires(pre):  shadow-utils



%description
Cloudify's REST Service.



%prep


%build

virtualenv /opt/manager/env

default_version=%{CORE_BRANCH}
export REST_SERVICE_BUILD=True

/opt/manager/env/bin/pip install --upgrade pip setuptools
/opt/manager/env/bin/pip install git+https://github.com/cloudify-cosmo/cloudify-dsl-parser@4.2#egg=cloudify-dsl-parser==4.2
/opt/manager/env/bin/pip install --upgrade "${RPM_SOURCE_DIR}/rest-service"


# Jinja2 includes 2 files which will only be imported if async is available,
# but rpmbuild's brp-python-bytecompile falls over when it finds them. Here
# we remove them.
rm /opt/manager/env/lib/python2.7/site-packages/jinja2/async*.py


%install

mkdir -p %{buildroot}/opt/manager
mv /opt/manager/env %{buildroot}/opt/manager

mkdir -p %{buildroot}/opt/manager/resources/
cp -R "${RPM_SOURCE_DIR}/resources/rest-service/cloudify/" "%{buildroot}/opt/manager/resources/"

# Create the log dir
mkdir -p %{buildroot}/var/log/cloudify/rest


%pre

groupadd -fr cfyuser
getent passwd cfyuser >/dev/null || useradd -r -g cfyuser -d /etc/cloudify -s /sbin/nologin cfyuser


%post



%preun
%postun


%files

%defattr(-,root,root)
/opt/manager

%attr(750,cfyuser,adm) /var/log/cloudify/rest
