#!/usr/bin/env bash

echo "#############################################################"
echo "Installing cloudify manager installer..."
echo "#############################################################"

sudo chown $USER:$USER -R /opt/cloudify-bootstrap
pushd /opt/cloudify-bootstrap
    sudo python get-pip.py
    sudo pip install ./cloudify-local-bootstrap
popd

echo "#############################################################"
echo "Cloudify installer is ready!"
echo "Edit /opt/cloudify-bootstrap/config.json, and run cfy_install"
echo "#############################################################"