#/bin/bash -e

function build_rpm() {
    echo "Building RPM..."
    sudo yum install -y epel-release
    sudo yum install -y mock
    sudo usermod -a -G mock $USER
    newgrp mock
    # allow network access during the build (we have to download packages from pypi)
    echo -e "\nconfig_opts['rpmbuild_networking'] = True\n" | sudo tee -a /etc/mock/site-defaults.cfg

    # Build the source RPM
    mock --buildsrpm --spec cloudify-manager/packaging/restservice/build.spec --sources cloudify-manager/
    cp /var/lib/mock/epel-7-x86_64/result/*.src.rpm .
    # mock strongly assumes that root is not required for building RPMs.
    # Here we work around that assumption by changing the onwership of /opt
    # inside the CHROOT to the mockbuild user
    mock --chroot -- chown -R mockbuild /opt
    # Build the RPM
    mock *.src.rpm --no-clean
}


# VERSION/PRERELEASE are exported to follow with our standard of exposing them as env vars. They are not used.
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


install_common_prereqs &&
build_rpm &&
cd /tmp/x86_64 && create_md5 "rpm" &&
[ -z ${AWS_ACCESS_KEY} ] || upload_to_s3 "rpm" && upload_to_s3 "md5"
