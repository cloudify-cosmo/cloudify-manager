#/bin/bash -e

function build_rpm() {
    echo "Building RPM..."
    sudo yum install -y rpm-build redhat-rpm-config
    sudo yum install -y python-devel gcc
    sudo mkdir -p /root/rpmbuild/{BUILD,RPMS,SOURCES,SPECS,SRPMS}
    sudo cp /vagrant/elasticsearch_curator/build.spec /root/rpmbuild/SPECS
    sudo rpmbuild -ba /root/rpmbuild/SPECS/build.spec
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

CORE_TAG_NAME="4.0m9"

AWS_ACCESS_KEY_ID=$1
AWS_ACCESS_KEY=$2
export REPO=$3
export GITHUB_USERNAME=$4
export GITHUB_PASSWORD=$5
export AWS_S3_PATH="org/cloudify3/components"

curl -u $GITHUB_USERNAME:$GITHUB_PASSWORD https://raw.githubusercontent.com/cloudify-cosmo/$REPO/new-versioning/packages-urls/provision.sh -o ./common-params.sh &&
source common-params.sh &&
curl https://raw.githubusercontent.com/cloudify-cosmo/cloudify-packager/new-versioning/common/provision.sh -o ./common-provision.sh &&
source common-provision.sh

install_common_prereqs &&
build_rpm &&
cd /tmp/x86_64 && create_md5 "rpm" &&
[ -z ${AWS_ACCESS_KEY} ] || upload_to_s3 "rpm" && upload_to_s3 "md5"
