#!/usr/bin/env bash

function create_install_rpm() {
    # Get the manager single tar (can be either community or premium)
    MANAGER_RESOURCES_URL=`curl -u $GITHUB_USERNAME:$GITHUB_PASSWORD https://raw.githubusercontent.com/cloudify-cosmo/${REPO}/${CORE_BRANCH}/packages-urls/manager-single-tar.yaml`

    curl -L https://raw.githubusercontent.com/cloudify-cosmo/cloudify-manager-install/${CORE_BRANCH}/packaging/create_rpm.sh -o /tmp/create_rpm.sh
    chmod +x /tmp/create_rpm.sh
    /tmp/create_rpm.sh ${MANAGER_RESOURCES_URL}
}

export CORE_TAG_NAME="4.2"
export CORE_BRANCH="master"
AWS_ACCESS_KEY_ID=$1
AWS_ACCESS_KEY=$2
export REPO=$3
export GITHUB_USERNAME=$4
export GITHUB_PASSWORD=$5

curl -u $GITHUB_USERNAME:$GITHUB_PASSWORD https://raw.githubusercontent.com/cloudify-cosmo/${REPO}/${CORE_BRANCH}/packages-urls/common_build_env.sh -o ./common_build_env.sh &&
source common_build_env.sh &&
curl https://raw.githubusercontent.com/cloudify-cosmo/cloudify-packager/${CORE_BRANCH}/common/provision.sh -o ./common-provision.sh &&
source common-provision.sh

echo "AWS_S3_PATH=$AWS_S3_PATH"

install_common_prereqs &&
create_install_rpm &&
cd /tmp && create_md5 "rpm" &&
[ -z ${AWS_ACCESS_KEY} ] || upload_to_s3 "rpm" && upload_to_s3 "md5"