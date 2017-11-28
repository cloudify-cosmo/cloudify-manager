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

if [ $# -eq 0 ]; then
    echo "You need to provide a resource URL for the script to work"
    exit 1
fi

print_line "Validating user has sudo permissions..."
sudo -n true

MANAGER_RESOURCES_URL=$1
INSTALL_PIP=${2:-true}
BRANCH=${3:-master}

if [ ${INSTALL_PIP} = "true" ]; then
    print_line "Installing pip..."
    curl -O https://bootstrap.pypa.io/get-pip.py
    sudo python get-pip.py
else
    print_line "Validating pip is installed..."
    set +e
    pip
    if [ $? -ne "0" ]; then
       echo "pip is not installed but is required"
       exit 1
    fi
    set -e
fi

print_line "Installing fpm dependencies..."
sudo yum install -y -q ruby-devel gcc make rpm-build rubygems

print_line "Installing fpm..."
gem install --no-ri --no-rdoc fpm

print_line "Installing pex..."
sudo pip install pex

cd /tmp

mkdir -p tmp-install-rpm

pushd tmp-install-rpm

    # Anything inside these inner directory will be mapped on the manager to
    # /opt/cloudify-manager-install and /opt/cloudify, respectively.
    # Anything *outside* of these must be mapped manually when running fpm
    # (e.g. see cfy_manager mapping)
    mkdir -p cloudify-manager-install cloudify

    pushd cloudify-manager-install
        print_line "Getting config.yaml from the repo..."
        curl -O https://raw.githubusercontent.com/cloudify-cosmo/cloudify-manager-install/${BRANCH}/config.yaml
    popd

    pushd cloudify
        print_line "Downloading and extracting cloudify manager resources tar..."
        curl -o manager-resources.tar.gz ${MANAGER_RESOURCES_URL}
        mkdir sources
        tar -xzf manager-resources.tar.gz -C sources --strip=1
        rm manager-resources.tar.gz
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
RPMLOC=$(fpm \
  -s dir \
  -t rpm \
  -n cloudify-manager-install \
  --force ${VERSION:+ -v "${VERSION}"} ${PRERELEASE:+ --iteration "${PRERELEASE}"} \
  --after-install ./tmp-install-rpm/install.sh \
  --config-files /opt/cloudify-manager-install/config.yaml \
  ./tmp-install-rpm/cfy_manager=/usr/bin/cfy_manager \
  ./tmp-install-rpm/cloudify-manager-install=/opt \
  ./tmp-install-rpm/cloudify=/opt \
)
# Maintain something close to standard output but allow printing the actual location
echo ${RPMLOC}

print_line "Cleaning up..."
rm -rf tmp-install-rpm

print_line "RPM created: $(pwd)/$(echo ${RPMLOC} | grep -oE 'path[^ ]+' | cut -d '"' -f2)"
