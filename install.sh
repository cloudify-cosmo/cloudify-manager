#!/usr/bin/env bash

echo "#############################################################"
echo "Installing cloudify manager installer..."
echo "#############################################################"

# Using $SUDO_USER instead of $USER here because fpm runs the script as sudo
sudo chown $SUDO_USER:$SUDO_USER -R /opt/cloudify-bootstrap
sudo yum install -y /opt/cloudify-bootstrap/cloudify-local-bootstrap-*.noarch.rpm

echo "#############################################################"
echo "Cloudify installer is ready!"
echo "Edit /opt/cloudify-bootstrap/config.json, and run cfy_install"
echo "#############################################################"