#!/usr/bin/env bash

# Colors
ESC_SEQ="\x1b["
COL_RESET=$ESC_SEQ"39;49;00m"
COL_RED=$ESC_SEQ"31;01m"
COL_GREEN=$ESC_SEQ"32;01m"
COL_YELLOW=$ESC_SEQ"33;01m"
COL_BLUE=$ESC_SEQ"34;01m"
COL_MAGENTA=$ESC_SEQ"35;01m"
COL_CYAN=$ESC_SEQ"36;01m"

LINE="-------------------------------------------------------------"

function print_line() {
  echo -e "$COL_YELLOW $LINE $COL_RESET"
  echo -e "$COL_BLUE $1 $COL_RESET"
  echo -e "$COL_YELLOW $LINE $COL_RESET"
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

print_line "Installing pip and pex..."
curl https://bootstrap.pypa.io/get-pip.py -o get-pip.py
sudo python get-pip.py
sudo pip install pex

mkdir -p cloudify-manager-install

pushd cloudify-manager-install

    print_line "Downloading cloudify manager resources tar..."
    curl ${MANAGER_RESOURCES_URL} -o ${MANAGER_RESOURCES_TAR}

    print_line "Creating cfy_manager executable..."
    pex https://github.com/mcouthon/cloudify-manager-install/archive/master.tar.gz -o cfy_manager -m cfy_manager.main --disable-cache

    print_line "Getting install.sh and config.yaml from the repo..."
    curl https://raw.githubusercontent.com/mcouthon/cloudify-manager-install/master/packaging/install.sh -o install.sh
    curl https://raw.githubusercontent.com/mcouthon/cloudify-manager-install/master/config.yaml -o config.yaml
popd

print_line "Creating rpm..."
# -s dir: Source is a directory
# -t rpm: Output is an rpm
# -n <>: The name of the package
# -x <>: Files to exclude
# --prefix /opt: The rpm will be extracted to /opt
# --after-install: A script to run after yum install
# PATH_1=PATH_2: After yum install, move the file in PATH_1 to PATH_2
# cloudify-manager-install: The directory from which the rpm will be created
fpm -s dir -t rpm -n cloudify-manager-install --force -v 0.3 --after-install cloudify-manager-install/install.sh cloudify-manager-install/cfy_manager=/usr/bin/cfy_manager cloudify-manager-install/${MANAGER_RESOURCES_TAR}=/opt/cloudify-manager-install/${MANAGER_RESOURCES_TAR} cloudify-manager-install/config.yaml=/opt/cloudify-manager-install/config.yaml cloudify-manager-install

print_line "Cleaning up..."
rm -rf cloudify-manager-install