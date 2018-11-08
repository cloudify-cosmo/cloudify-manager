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
    local repo=$3
    local build=$4

    curl -L -u $GITHUB_USERNAME:$GITHUB_PASSWORD https://github.com/cloudify-cosmo/${REPO}/archive/${CORE_BRANCH}.tar.gz > /vagrant/${REPO}.tar.gz
    tar -zxvf /vagrant/${REPO}.tar.gz -C /vagrant

    echo "Creating resource directory..."
    mkdir -p /tmp/cloudify-manager-resources/agents
    cd /tmp
    pushd /tmp/cloudify-manager-resources
        echo "Downloading manager component packages..."
        download_resources '/vagrant/'${REPO}'-'${CORE_BRANCH}'/packages-urls/manager-packages.yaml'
        pushd agents
            echo "Downloading agent packages..."
            download_resources '/vagrant/'${REPO}'-'${CORE_BRANCH}'/packages-urls/agent-packages.yaml'
        popd
    popd

    echo "Generating resources archive..."

    tar -cvzf /tmp/cloudify-manager-resources_${version}-${prerelease}.tar.gz cloudify-manager-resources
    rm -rf /tmp/cloudify-manager-resources
}


export CORE_TAG_NAME="4.3.4"
export CORE_BRANCH="4.3.4-build"
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
create_resources_tar $VERSION $PRERELEASE $BUILD &&
cd /tmp && create_md5 "tar.gz" &&
[ -z ${AWS_ACCESS_KEY} ] || upload_to_s3 "tar.gz" && upload_to_s3 "md5"