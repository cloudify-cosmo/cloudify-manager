#!/usr/bin/env bash

cd /tmp

echo "Installing fpm dependencies..."
sudo yum install -y -q ruby-devel gcc make rpm-build rubygems

echo "Installing other dependencies..."
sudo yum install -y -q git

echo "Installing fpm..."
gem install --no-ri --no-rdoc fpm

mkdir -p cloudify-bootstrap

echo "Downloading cloudify manager resources tar..."
curl http://cloudify-release-eu.s3.amazonaws.com/cloudify/4.2.0/.dev1-release/cloudify-manager-resources_4.2.0-.dev1.tar.gz -o cloudify-bootstrap/cloudify-manager-resources_4.2.0-.dev1.tar.gz

echo "Cloning local bootstrap repo..."
git clone https://github.com/mcouthon/cloudify-local-bootstrap.git cloudify-bootstrap/cloudify-local-bootstrap

echo "Getting pip..."
curl https://bootstrap.pypa.io/get-pip.py -o cloudify-bootstrap/get-pip.py

echo "Creating rpm..."
fpm -s dir -t rpm -n cloudify-bootstrap -v 1.0 -x "*.pyc" -x ".*" --prefix /opt --after-install cloudify-bootstrap/cloudify-local-bootstrap/install.sh cloudify-bootstrap