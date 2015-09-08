%define _rpmdir /tmp

Name:           elasticsearch-curator
Version:        3.2.3
Release:        1
Summary:        Elasticsearch Curator Package for Cloudify
Group:          Applications/Multimedia
License:        Apache 2.0
URL:            https://github.com/elastic/curator
Vendor:         Elastic
Prefix:         %{_prefix}
Packager:       Gigaspaces Inc.
BuildRoot:      %{_tmppath}/%{name}-root

%description
Have indices in Elasticsearch? This is the tool for you!
Like a museum curator manages the exhibits and collections on display, Elasticsearch Curator helps you curate, or manage your indices.

%prep
set +e
pip=$(which pip)
set -e

[ ! -z $pip ] || sudo curl --show-error --silent --retry 5 https://bootstrap.pypa.io/get-pip.py | sudo python
sudo pip install wheel==0.24.0

%build

%install
sudo pip wheel %{name}==%{version} --wheel-dir %{buildroot}/var/wheels/%{name}

%pre
# mkdir -p /var/wheels/${buildroot}

%post
pip install --use-wheel --no-index --find-links=/var/wheels/%{name} %{name}==%{version}

%preun

%postun
pip uninstall -y %{name}

echo "Note that the Python module 'click' and its dependencies will not be uninstalled as they might be used elsewhere."
echo "Note that the Python module 'elasticsearch' and its dependencies will not be uninstalled as they might be used elsewhere."
echo "Note that the Python module 'urllib3' and its dependencies will not be uninstalled as they might be used elsewhere."

rm -rf /var/wheels/${name}

%files
%defattr(-,root,root)
/var/wheels/%{name}/*.whl