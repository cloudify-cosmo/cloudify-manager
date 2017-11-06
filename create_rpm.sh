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
    MANAGER_RESOURCES_URL="${CLOUDIFY_RELEASE_URL}/17.10.29/release/cloudify-manager-resources_17.10.29-community.tar.gz"
    MANAGER_RESOURCES_TAR="cloudify-manager-resources_17.10.29-community.tar.gz"
else
    print_line "Working in Premium edition"

    MANAGER_RESOURCES_URL="${CLOUDIFY_RELEASE_URL}/4.2.0/ga-release/cloudify-manager-resources_4.2.0-ga.tar.gz"
    MANAGER_RESOURCES_TAR="cloudify-manager-resources_4.2.0-ga.tar.gz"
fi

cd /tmp

print_line "Installing fpm dependencies..."
sudo yum install -y -q ruby-devel gcc make rpm-build rubygems

print_line "Installing fpm..."
gem install --no-ri --no-rdoc fpm

mkdir -p cloudify-bootstrap

pushd cloudify-bootstrap

    print_line "Downloading cloudify manager resources tar..."
    curl ${MANAGER_RESOURCES_URL} -o ${MANAGER_RESOURCES_TAR}

    print_line "Downloading local bootstrap repo..."
    curl -L https://github.com/mcouthon/cloudify-local-bootstrap/archive/master.tar.gz | tar xz

    # The root dir inside a Github tarball is in a repo-branch format
    # (e.g. repo-master), so we move it inside our cloudify-bootstrap folder,
    # with the correct name
    mv cloudify-local-bootstrap-* cloudify-local-bootstrap

    print_line "Creating installation package RPM"
    # The bdist_rpm needs to be executed in the same folder (for some reason)
    pushd cloudify-local-bootstrap
        python setup.py bdist --format=gztar
    popd

    # Moving the only necessary parts to the top level of the RPM
    mv cloudify-local-bootstrap/dist/cloudify-local-bootstrap-*.tar.gz .
    mv cloudify-local-bootstrap/install.sh .
    mv cloudify-local-bootstrap/config.json .

    rm -rf cloudify-local-bootstrap

popd

print_line "Creating rpm..."
# -s dir: Source is a directory
# -t rpm: Output is an rpm
# -n <>: The name of the package
# -x <>: Files to exclude
# --prefix /opt: The rpm will be extracted to /opt
# --after-install: A script to run after yum install
# PATH_1=PATH_2: After yum install, move the file in PATH_1 to PATH_2
# cloudify-bootstrap: The directory from which the rpm will be created
fpm -s dir -t rpm -n cloudify-bootstrap -v 1.0 -x "*.pyc" -x ".*" -x "*tests" --prefix /opt --after-install cloudify-bootstrap/install.sh cloudify-bootstrap

print_line "Cleaning up..."
rm -rf cloudify-bootstrap