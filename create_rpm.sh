#!/usr/bin/env bash

function print_line() {
  echo '-------------------------------------------------------------'
  echo $1
  echo '-------------------------------------------------------------'
}

CLOUDIFY_RELEASE_URL="http://cloudify-release-eu.s3.amazonaws.com/cloudify"
MANAGER_RESOURCES_DIR="cloudify-manager-resources"

if [ ${COMMUNITY_EDITION} ]; then
    print_line "Working in Community edition"

    CLI_PACKAGE_URL="${CLOUDIFY_RELEASE_URL}/17.10.5/release/cloudify-17.10.5~community.el6.x86_64.rpm"
    CLI_PACKAGE="cloudify-cli-17.10.5~community.el6.x86_64.rpm"

    MANAGER_RESOURCES_URL="${CLOUDIFY_RELEASE_URL}/17.10.5/release/cloudify-manager-resources_17.10.5-community.tar.gz"
    MANAGER_RESOURCES_TAR="cloudify-manager-resources_17.10.5-community.tar.gz"
else
    print_line "Working in Premium edition"

    CLI_PACKAGE_URL="${CLOUDIFY_RELEASE_URL}/4.2.0/.dev1-release/cloudify-4.2.0~.dev1.el6.x86_64.rpm"
    CLI_PACKAGE="cloudify-cli-4.2.0~.dev1.el6.x86_64.rpm"

    MANAGER_RESOURCES_URL="${CLOUDIFY_RELEASE_URL}/4.2.0/.dev1-release/cloudify-manager-resources_4.2.0-.dev1.tar.gz"
    MANAGER_RESOURCES_TAR="cloudify-manager-resources_4.2.0-.dev1.tar.gz"
fi

cd /tmp

print_line "Installing fpm dependencies..."
sudo yum install -y -q ruby-devel gcc make rpm-build rubygems

print_line "Installing fpm..."
gem install --no-ri --no-rdoc fpm

mkdir -p cloudify-bootstrap

print_line "Downloading cloudify manager resources tar..."
curl ${MANAGER_RESOURCES_URL} -o ${MANAGER_RESOURCES_TAR}

# TODO: Remove this when the CLI is a part of the single tar
print_line "Downloading CLI package..."
curl ${CLI_PACKAGE_URL} -o ${CLI_PACKAGE}

print_line "Adding CLI package to single tar..."
tar -xf ${MANAGER_RESOURCES_TAR}
mv ${CLI_PACKAGE} ${MANAGER_RESOURCES_DIR}
tar -czf ${MANAGER_RESOURCES_TAR} ${MANAGER_RESOURCES_DIR}
rm -rf ${MANAGER_RESOURCES_DIR}
mv ${MANAGER_RESOURCES_TAR} cloudify-bootstrap

print_line "Downloading local bootstrap repo..."
curl -L https://github.com/mcouthon/cloudify-local-bootstrap/archive/master.tar.gz | tar xz

# The root dir inside a Github tarball is in a repo-branch format
# (e.g. repo-master), so we move it inside our cloudify-bootstrap folder,
# with the correct name
mv cloudify-local-bootstrap-* cloudify-bootstrap/cloudify-local-bootstrap

print_line "Getting pip..."
curl https://bootstrap.pypa.io/get-pip.py -o cloudify-bootstrap/get-pip.py

print_line "Creating rpm..."
# -s dir: Source is a directory
# -t rpm: Output is an rpm
# -n <>: The name of the package
# -x <>: Files to exclude
# --prefix /opt: The rpm will be extracted to /opt
# --after-install: A script to run after yum install
# PATH_1=PATH_2: After yum install, move the file in PATH_1 to PATH_2
# cloudify-bootstrap: The directory from which the rpm will be created
fpm -s dir -t rpm -n cloudify-bootstrap -v 1.0 -x "*.pyc" -x ".*" -x "*tests" --prefix /opt --after-install cloudify-bootstrap/cloudify-local-bootstrap/install.sh cloudify-bootstrap/cloudify-local-bootstrap/config.json=cloudify-bootstrap/config.json cloudify-bootstrap

print_line "Cleaning up..."
rm -rf cloudify-bootstrap