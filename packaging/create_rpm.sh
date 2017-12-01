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

function exit_with_sadness() {
  echo ${1} >&2
  exit 1
}

function validate_args() {
  # We're using this ugly construct twice now. If we need it once more we should probably make it a function
  if [[ "${INSTALL_PIP}" != true ]] && [[ "${INSTALL_PIP}" != false ]]; then
    exit_with_sadness "Install pip argument must be either 'true' or 'false', but was: ${INSTALL_PIP}"
  fi

  # About the only definitely 'bad' branch is if someone deliberately feeds an empty string
  # It shouldn't be possible to reach this while we're defaulting but it's worth guarding against in case of later modifications.
  if [[ -z "${BRANCH}" ]]; then
    exit_with_sadness "Specifying an empty string as the branch will cause problems."
  fi

  if [[ "${COMMUNITY_OR_PREMIUM}" != community ]] && [[ "${COMMUNITY_OR_PREMIUM}" != premium ]]; then
    exit_with_sadness "Community/premium argument must be either 'community' or 'premium' but was: ${COMMUNITY_OR_PREMIUM}"
  fi
}

function get_repo() {
  case ${COMMUNITY_OR_PREMIUM} in
    community)
      repo=cloudify-versions
      ;;
    premium)
      repo=cloudify-premium
      ;;
    *)
      exit_with_sadness "Could not determine which repository to retrieve."
  esac

  full_repo_path="cloudify-cosmo/${repo}.git"

  if [[ "${COMMUNITY_OR_PREMIUM}" == community ]]; then
    # We don't need GitHub credentials for the cloudify-versions repo
    git_repo="https://github.com/${full_repo_path}"
  else
      # vars supported for compatibility with current jenkins build approach
      GITHUB_USERNAME=${GITHUB_USERNAME:-""}
      GITHUB_PASSWORD=${GITHUB_PASSWORD:-""}
      if [[ -n "${GITHUB_USERNAME}" ]]; then
        # If we have github credentials in the environment we will use them to fetch the repo
        git_repo="https://${GITHUB_USERNAME}:${GITHUB_PASSWORD}@github.com/${full_repo_path}"
      else
        # If not, we will assume SSH keys will work
        git_repo="git@github.com:${full_repo_path}"
      fi
  fi

  git clone ${git_repo} . --branch=${BRANCH} --single-branch
}

function download_resources() {
    local resources_file=$1

    while read file; do
      echo "Downloading ${file}..."
      curl --retry 10 --fail --silent --show-error --location -O $file
    done < $resources_file
}

COMMUNITY_OR_PREMIUM=${1:-premium}
INSTALL_PIP=${2:-true}
BRANCH=${3:-master}
LOCAL_PATH=${4:-""}

validate_args

PRERELEASE=${PRERELEASE:-${COMMUNITY_OR_PREMIUM}}

print_line "Validating user has sudo permissions..."
sudo -n true

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

print_line "Installing dependencies..."
# fpm requires ruby-devel, gcc, make, rpm-build, rubygems
# This script requires git
sudo yum install -y -q ruby-devel gcc make rpm-build rubygems git

print_line "Installing fpm..."
gem install --no-ri --no-rdoc fpm

print_line "Installing pex..."
sudo pip install pex

cd /tmp

mkdir -p tmp-install-rpm

pushd tmp-install-rpm
  # Anything inside this inner directory will be mapped on the manager to
  # /opt/cloudify
  # Anything *outside* of these must be mapped manually when running fpm
  # (e.g. see cfy_manager mapping)
  mkdir -p cloudify/sources

  pushd cloudify
    print_line "Getting config.yaml from the repo..."
    if [[ -n "${LOCAL_PATH}" ]]; then
        cp ${LOCAL_PATH}/config.yaml .
    else
        curl -O https://raw.githubusercontent.com/cloudify-cosmo/cloudify-manager-install/${BRANCH}/config.yaml
    fi
    if [[ "${COMMUNITY_OR_PREMIUM}" == premium ]]; then
      sed -i 's/premium_edition: set_by_installer_builder/premium_edition: true/' config.yaml
    else
      sed -i 's/premium_edition: set_by_installer_builder/premium_edition: false/' config.yaml
    fi
  popd

  pushd cloudify/sources
    mkdir versions -p
    pushd versions
      get_repo
    popd
    print_line "Downloading cloudify manager resources..."
    download_resources "versions/packages-urls/manager-packages.yaml"

    mkdir agents -p
    pushd agents
      print_line "Downloading cloudify agent resources..."
      download_resources "../versions/packages-urls/agent-packages.yaml"
    popd
    rm -rf versions
  popd

  print_line "Creating cfy_manager executable and getting the install.sh script..."
  if [[ -n "${LOCAL_PATH}" ]]; then
    pex ${LOCAL_PATH} -o cfy_manager -m cfy_manager.main --disable-cache
    cp ${LOCAL_PATH}/packaging/install.sh .
  else
    pex https://github.com/cloudify-cosmo/cloudify-manager-install/archive/${BRANCH}.tar.gz -o cfy_manager -m cfy_manager.main --disable-cache
    curl -O https://raw.githubusercontent.com/cloudify-cosmo/cloudify-manager-install/${BRANCH}/packaging/install.sh
  fi
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
RPMLOC=$(fpm \
  -s dir \
  -t rpm \
  -n cloudify-manager-install \
  --force ${VERSION:+ -v "${VERSION}"} ${PRERELEASE:+ --iteration "${PRERELEASE}"} \
  --after-install ./tmp-install-rpm/install.sh \
  --config-files /opt/cloudify/config.yaml \
  ./tmp-install-rpm/cfy_manager=/usr/bin/cfy_manager \
  ./tmp-install-rpm/cloudify=/opt \
)
# Maintain something close to standard output but allow printing the actual location
echo ${RPMLOC}

print_line "Cleaning up..."
rm -rf tmp-install-rpm

print_line "RPM created: $(pwd)/$(echo ${RPMLOC} | grep -oE 'path[^ ]+' | cut -d '"' -f2)"
