#/bin/bash

sudo yum install -y rpm-build redhat-rpm-config
sudo mkdir -p /root/rpmbuild/{BUILD,RPMS,SOURCES,SPECS,SRPMS}
sudo cp /vagrant/elasticsearch_curator/build.spec /root/rpmbuild/SPECS
sudo rpmbuild -ba /root/rpmbuild/SPECS/build.spec

# rpm can be found under /root/rpmbuild/RPMS/x86_64/elasticsearch-curator-3.2.3-1.x86_64.rpm