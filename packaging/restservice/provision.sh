#/bin/bash -e

function build_rpm() {
    echo "Building RPM..."
    sudo yum install -y rpm-build redhat-rpm-config
    sudo yum install -y python-devel gcc
    sudo mkdir -p /root/rpmbuild/{BUILD,RPMS,SOURCES,SPECS,SRPMS}
    sudo cp /vagrant/restservice/build.spec /root/rpmbuild/SPECS
    sudo rpmbuild -ba /root/rpmbuild/SPECS/build.spec \
        --define "VERSION $VERSION" \
        --define "PRERELEASE $PRERELEASE" \
        --define "BUILD $BUILD" \
        --define "CORE_TAG_NAME $CORE_TAG_NAME" \
        --define "PREMIUM $PREMIUM" \
        --define "PREMIUM_FOLDER $PREMIUM_FOLDER" \
        --define "GITHUB_USERNAME $GITHUB_USERNAME" \
        --define "GITHUB_PASSWORD $GITHUB_PASSWORD"

    # This is the UGLIEST HACK EVER!
    # Since rpmbuild spec files cannot receive a '-' in their version,
    # we do this... thing and replace an underscore with a dash.
    # cd /tmp/x86_64 &&
    # sudo mv *.rpm $(ls *.rpm | sed 's|_|-|g')
}

# VERSION/PRERELEASE/BUILD are exported to follow with our standard of exposing them as env vars. They are not used.
CORE_TAG_NAME="4.0m7"
curl https://raw.githubusercontent.com/cloudify-cosmo/cloudify-packager/$CORE_TAG_NAME/common/provision.sh -o ./common-provision.sh &&
source common-provision.sh

AWS_ACCESS_KEY_ID=$1
AWS_ACCESS_KEY=$2
export PREMIUM=$3
export GITHUB_USERNAME=$4
export GITHUB_PASSWORD=$5

echo "PREMIUM=$PREMIUM"
if [ "$PREMIUM" == "true" ]; then
    export AWS_S3_PATH=$AWS_S3_PATH"/"$PREMIUM_FOLDER
fi
echo "AWS_S3_PATH=$AWS_S3_PATH"

install_common_prereqs &&
build_rpm &&
cd /tmp/x86_64 && create_md5 "rpm" &&
[ -z ${AWS_ACCESS_KEY} ] || upload_to_s3 "rpm" && upload_to_s3 "md5"
