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
        --define "PLUGINS_TAG_NAME $PLUGINS_TAG_NAME"
    # This is the UGLIEST HACK EVER!
    # Since rpmbuild spec files cannot receive a '-' in their version,
    # we do this... thing and replace an underscore with a dash.
    # cd /tmp/x86_64 &&
    # sudo mv *.rpm $(ls *.rpm | sed 's|_|-|g')
}

function generate_checksum() {
    echo "Generating md5 checksum..."
    cd /tmp/x86_64 && md5sum=$(md5sum *.rpm) && echo $md5sum | sudo tee ${md5sum##* }.md5
}

function upload_to_s3() {
    ###
    # This will upload both the artifact and md5 files to the relevant bucket.
    # Note that the bucket path is also appended the version.
    ###
    echo "Uploading to s3..."
    sudo pip install s3cmd==1.5.2
    sudo s3cmd put --force --acl-public --access_key=${AWS_ACCESS_KEY_ID} --secret_key=${AWS_ACCESS_KEY} \
        --no-preserve --progress --human-readable-sizes --check-md5 *.rpm* s3://${AWS_S3_BUCKET_PATH}/
}

# VERSION/PRERELEASE/BUILD are exported to follow with our standard of exposing them as env vars. They are not used.
export VERSION="3.3.0"
export PRERELEASE="m7"
export BUILD="277"
CORE_TAG_NAME="3.3.0m7"
PLUGINS_TAG_NAME="1.3m7"

AWS_ACCESS_KEY_ID=$1
AWS_ACCESS_KEY=$2
AWS_S3_BUCKET_PATH="gigaspaces-repository-eu/org/cloudify3/${VERSION}/${PRERELEASE}-RELEASE"

echo "VERSION: ${VERSION}"
echo "PRERELEASE: ${PRERELEASE}"
echo "BUILD: ${BUILD}"
echo "CORE_TAG_NAME: ${CORE_TAG_NAME}"
echo "PLUGINS_TAG_NAME: ${PLUGINS_TAG_NAME}"
echo "AWS_S3_BUCKET_PATH: ${AWS_S3_BUCKET_PATH}"

build_rpm
generate_checksum
[ -z ${AWS_ACCESS_KEY} ] || upload_to_s3