#!/usr/bin/env bash

set -eu

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

MANAGER_RESOURCES_URL=$1
BRANCH=${2:-master}

print_line "Installing fpm dependencies..."
sudo yum install -y -q ruby-devel gcc make rpm-build rubygems

print_line "Installing fpm..."
gem install --no-ri --no-rdoc fpm

print_line "Installing pex..."
sudo pip install pex

cd /tmp

mkdir -p tmp-install-rpm

pushd tmp-install-rpm

    # Anything inside this inner directory will be mapped on the manager to
    # /opt/cloudify-manager-install. Anything *outside* it needs to be
    # mapped manually when running fpm
    mkdir -p cloudify-manager-install

    pushd cloudify-manager-install
        print_line "Downloading cloudify manager resources tar..."
        curl -O ${MANAGER_RESOURCES_URL}

        print_line "Getting config.yaml from the repo..."
        curl -O https://raw.githubusercontent.com/cloudify-cosmo/cloudify-manager-install/${BRANCH}/config.yaml
    popd

    print_line "Creating cfy_manager executable..."
    pex https://github.com/cloudify-cosmo/cloudify-manager-install/archive/${BRANCH}.tar.gz -o cfy_manager -m cfy_manager.main --disable-cache

    print_line "Getting install.sh from the repo..."
    curl -O https://raw.githubusercontent.com/cloudify-cosmo/cloudify-manager-install/${BRANCH}/packaging/install.sh
popd

print_line "Creating rpm..."
# -s dir: Source is a directory
# -t rpm: Output is an rpm
# -n <>: The name of the package
# -x <>: Files to exclude
# -v: Version (e.g. 4.2.0)
# --iteration: Release (e.g. dev1)
# --prefix /opt: The rpm will be extracted to /opt
# --after-install: A script to run after yum install
# PATH_1=PATH_2: After yum install, move the file in PATH_1 to PATH_2
# cloudify-manager-install: The directory from which the rpm will be created
fpm -s dir -t rpm -n cloudify-manager-install --force ${VERSION:+ -v "${VERSION}"} ${PRERELEASE:+ --iteration "${PRERELEASE}"} --after-install ./tmp-install-rpm/install.sh ./tmp-install-rpm/cfy_manager=/usr/bin/cfy_manager ./tmp-install-rpm/cloudify-manager-install=/opt

print_line "Cleaning up..."
rm -rf tmp-install-rpm