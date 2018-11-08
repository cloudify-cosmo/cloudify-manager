#/bin/bash -e

function build_rpm() {
    echo "Building RPM..."
    sudo yum -y update &&
    sudo yum install -y rpm-build redhat-rpm-config &&
    sudo yum install -y python-devel gcc libffi-devel openssl-devel &&
    sudo mkdir -p /root/rpmbuild/{BUILD,RPMS,SOURCES,SPECS,SRPMS}
    sudo cp /vagrant/restservice/build.spec /root/rpmbuild/SPECS
    sudo rpmbuild -ba /root/rpmbuild/SPECS/build.spec \
        --define "VERSION $VERSION" \
        --define "PRERELEASE $PRERELEASE" \
        --define "BUILD $BUILD" \
        --define "CORE_TAG_NAME $CORE_TAG_NAME" \
        --define "CORE_BRANCH $CORE_BRANCH" \
        --define "REPO $REPO" \
        --define "GITHUB_USERNAME $GITHUB_USERNAME" \
        --define "GITHUB_PASSWORD $GITHUB_PASSWORD"

    # This is the UGLIEST HACK EVER!
    # Since rpmbuild spec files cannot receive a '-' in their version,
    # we do this... thing and replace an underscore with a dash.
    # cd /tmp/x86_64 &&
    # sudo mv *.rpm $(ls *.rpm | sed 's|_|-|g')
}


# VERSION/PRERELEASE are exported to follow with our standard of exposing them as env vars. They are not used.
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


install_common_prereqs &&
build_rpm &&
cd /tmp/x86_64 && create_md5 "rpm" &&
[ -z ${AWS_ACCESS_KEY} ] || upload_to_s3 "rpm" && upload_to_s3 "md5"
