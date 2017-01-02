%define _rpmdir /tmp


Name:           cloudify-rest-service
Version:        %{VERSION}
Release:        %{PRERELEASE}
Summary:        Cloudify's REST Service
Group:          Applications/Multimedia
License:        Apache 2.0
URL:            https://github.com/cloudify-cosmo/cloudify-manager
Vendor:         Gigaspaces Inc.
Prefix:         %{_prefix}
Packager:       Gigaspaces Inc.
BuildRoot:      %{_tmppath}/%{name}-root



%description
Cloudify's REST Service.



%prep

set +e
pip=$(which pip)
set -e

[ ! -z $pip ] || sudo curl --show-error --silent --retry 5 https://bootstrap.pypa.io/get-pip.py | sudo python
sudo yum install -y git python-devel postgresql-devel openldap-devel gcc gcc-c++
sudo pip install virtualenv
sudo virtualenv /tmp/env
sudo /tmp/env/bin/pip install -U pip==9.0.1 && \
sudo /tmp/env/bin/pip install setuptools==32.3.0 && \
sudo /tmp/env/bin/pip install wheel==0.24.0 && \

%build
%install

export REST_SERVICE_BUILD=True

destination="/tmp/${RANDOM}.file"
curl --retry 10 --fail --silent --show-error --location https://github.com/cloudify-cosmo/cloudify-manager/archive/%{CORE_TAG_NAME}.tar.gz --create-dirs --output $destination && \
tar -xzf $destination --strip-components=1 -C "/tmp" && \

mkdir -p %{buildroot}/opt/manager/resources/
sudo cp -R "/tmp/resources/rest-service/cloudify/" "%{buildroot}/opt/manager/resources/"

# ldappy is being install without a specific version, until it'll be stable..

sudo /tmp/env/bin/pip wheel virtualenv --wheel-dir %{buildroot}/var/wheels/%{name} && \
sudo /tmp/env/bin/pip wheel --wheel-dir=%{buildroot}/var/wheels/%{name} --find-links=%{buildroot}/var/wheels/%{name} https://github.com/cloudify-cosmo/cloudify-dsl-parser/archive/%{CORE_TAG_NAME}.tar.gz && \
sudo /tmp/env/bin/pip wheel --wheel-dir=%{buildroot}/var/wheels/%{name} --find-links=%{buildroot}/var/wheels/%{name} https://github.com/cloudify-cosmo/cloudify-rest-client/archive/%{CORE_TAG_NAME}.tar.gz && \
sudo /tmp/env/bin/pip wheel --wheel-dir=%{buildroot}/var/wheels/%{name} --find-links=%{buildroot}/var/wheels/%{name} https://github.com/cloudify-cosmo/cloudify-plugins-common/archive/%{CORE_TAG_NAME}.tar.gz && \
sudo /tmp/env/bin/pip wheel --wheel-dir=%{buildroot}/var/wheels/%{name} --find-links=%{buildroot}/var/wheels/%{name} https://github.com/cloudify-cosmo/cloudify-script-plugin/archive/1.4.tar.gz && \
sudo /tmp/env/bin/pip wheel --wheel-dir=%{buildroot}/var/wheels/%{name} --find-links=%{buildroot}/var/wheels/%{name} https://github.com/cloudify-cosmo/cloudify-agent/archive/%{CORE_TAG_NAME}.tar.gz && \
sudo /tmp/env/bin/pip wheel --wheel-dir=%{buildroot}/var/wheels/%{name} --find-links=%{buildroot}/var/wheels/%{name} https://github.com/dusking/ldappy/archive/master.tar.gz && \
sudo /tmp/env/bin/pip wheel --wheel-dir=%{buildroot}/var/wheels/%{name} --find-links=%{buildroot}/var/wheels/%{name} https://github.com/apache/incubator-ariatosca/archive/0.1.0.tar.gz && \
sudo /tmp/env/bin/pip wheel --wheel-dir=%{buildroot}/var/wheels/%{name} --find-links=%{buildroot}/var/wheels/%{name} https://github.com/cloudify-cosmo/cloudify-aria-extensions/archive/master.tar.gz && \
echo "from build.spec  PREMIUM=%{PREMIUM}"
if [ "%{PREMIUM}" == "true" ]; then
    sudo /tmp/env/bin/pip wheel --wheel-dir=%{buildroot}/var/wheels/%{name} --find-links=%{buildroot}/var/wheels/%{name} https://%{GITHUB_USERNAME}:%{GITHUB_PASSWORD}@github.com/cloudify-cosmo/cloudify-premium/archive/%{CORE_TAG_NAME}.tar.gz
fi
sudo -E /tmp/env/bin/pip wheel --wheel-dir=%{buildroot}/var/wheels/%{name} --find-links=%{buildroot}/var/wheels/%{name} /tmp/rest-service


%pre
%post

export REST_SERVICE_BUILD=True

pip install --use-wheel --no-index --find-links=/var/wheels/%{name} virtualenv && \
if [ ! -d "/opt/manager/env" ]; then virtualenv /opt/manager/env; fi && \
/opt/manager/env/bin/pip install --upgrade --force-reinstall --use-wheel --no-index --find-links=/var/wheels/%{name} cloudify-dsl-parser --pre && \
/opt/manager/env/bin/pip install --upgrade --force-reinstall --use-wheel --no-index --find-links=/var/wheels/%{name} cloudify-rest-client --pre && \
/opt/manager/env/bin/pip install --upgrade --force-reinstall --use-wheel --no-index --find-links=/var/wheels/%{name} cloudify-plugins-common --pre && \
/opt/manager/env/bin/pip install --upgrade --force-reinstall --use-wheel --no-index --find-links=/var/wheels/%{name} cloudify-script-plugin --pre && \
/opt/manager/env/bin/pip install --upgrade --force-reinstall --use-wheel --no-index --find-links=/var/wheels/%{name} cloudify-agent --pre && \
/opt/manager/env/bin/pip install --upgrade --force-reinstall --use-wheel --no-index --find-links=/var/wheels/%{name} ldappy --pre && \
/opt/manager/env/bin/pip install --upgrade --force-reinstall --use-wheel --no-index --find-links=/var/wheels/%{name} aria --pre && \
/opt/manager/env/bin/pip install --upgrade --force-reinstall --use-wheel --no-index --find-links=/var/wheels/%{name} cloudify-aria-extensions --pre && \
/opt/manager/env/bin/pip install --upgrade --force-reinstall --use-wheel --no-index --find-links=/var/wheels/%{name} cloudify-rest-service --pre
if [ "%{PREMIUM}" == "true" ]; then
    /opt/manager/env/bin/pip install --upgrade --force-reinstall --use-wheel --no-index --find-links=/var/wheels/%{name} cloudify-premium --pre
fi
# sudo cp -R "/tmp/resources/rest-service/cloudify/" "/opt/manager/resources/"


%preun
%postun

rm -rf /opt/manager/resources
rm -rf /var/wheels/${name}


%files

%defattr(-,root,root)
/var/wheels/%{name}/*.whl
/opt/manager/resources