#/bin/bash -e


function download_resources() {
    local resources_file=$1

    while read file; do
      echo "Downloading ${file}..."
      curl --retry 10 --fail --silent --show-error --location -O $file
    done < $resources_file
}


function create_resources_tar() {
    local version=$1
    local prerelease=$2
    local build=$3

    curl -L -u $GITHUB_USERNAME:GITHUB_PASSWORD https://github.com/cloudify-cosmo/${REPO}/archive/${CORE_TAG_NAME}.tar.gz > /vagrant/cloudify-versions.tar.gz
    tar -zxvf /vagrant/cloudify-versions.tar.gz -C /vagrant

    echo "Creating resource directory..."
    mkdir -p /tmp/cloudify-manager-resources/agents
    cd /tmp
    pushd /tmp/cloudify-manager-resources
        echo "Downloading manager component packages..."
        download_resources '/vagrant/${REPO}-'${CORE_TAG_NAME}'/packages-urls/manager-packages-blueprint.yaml'
        pushd agents
            echo "Downloading agent packages..."
            download_resources '/vagrant/${REPO}-'${CORE_TAG_NAME}'/packages-urls/agent-packages-blueprint.yaml'
        popd
    popd

    echo "Generating resources archive..."

    tar -cvzf /tmp/cloudify-manager-resources_${version}-${prerelease}.tar.gz cloudify-manager-resources
    rm -rf /tmp/cloudify-manager-resources
}


CORE_TAG_NAME="4.0m9"

AWS_ACCESS_KEY_ID=$1
AWS_ACCESS_KEY=$2
export REPO=$3
export GITHUB_USERNAME=$4
export GITHUB_PASSWORD=$5

curl -u $GITHUB_USERNAME:GITHUB_PASSWORD https://raw.githubusercontent.com/cloudify-cosmo/$REPO/new-versioning/packages-urls/provision.sh -o ./common-params.sh &&
source common-params.sh &&
curl https://raw.githubusercontent.com/cloudify-cosmo/cloudify-packager/new-versioning/common/provision.sh -o ./common-provision.sh &&
source common-provision.sh

echo "AWS_S3_PATH=$AWS_S3_PATH"

install_common_prereqs &&
create_resources_tar $VERSION $PRERELEASE $BUILD &&
cd /tmp && create_md5 "tar.gz" &&
[ -z ${AWS_ACCESS_KEY} ] || upload_to_s3 "tar.gz" && upload_to_s3 "md5"
