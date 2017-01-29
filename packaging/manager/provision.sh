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

    echo "Creating resource directory..."
    mkdir -p /tmp/cloudify-manager-resources/agents
    cd /tmp
    pushd /tmp/cloudify-manager-resources
        echo "Downloading manager component packages..."
        download_resources '/vagrant/manager/manager-packages-blueprint.yaml'
        pushd agents
            echo "Downloading agent packages..."
            download_resources '/vagrant/manager/agent-packages-blueprint.yaml'
        popd
    popd

    echo "Generating resources archive..."
    # deleting as the current upload function finds more than one file
    tar -cvzf /tmp/cloudify-manager-resources_${version}-${prerelease}-b${build}.tar.gz cloudify-manager-resources
    rm -rf /tmp/cloudify-manager-resources
}


CORE_TAG_NAME="3.4.2"
curl https://raw.githubusercontent.com/cloudify-cosmo/cloudify-packager/$CORE_TAG_NAME/common/provision.sh -o ./common-provision.sh &&
source common-provision.sh

AWS_ACCESS_KEY_ID=$1
AWS_ACCESS_KEY=$2

install_common_prereqs &&
create_resources_tar $VERSION $PRERELEASE $BUILD &&
cd /tmp && create_md5 "tar.gz" &&
[ -z ${AWS_ACCESS_KEY} ] || upload_to_s3 "tar.gz" && upload_to_s3 "md5"
