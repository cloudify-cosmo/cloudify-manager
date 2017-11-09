#!/usr/bin/env bash

echo "###################################################################"
echo "Installing cloudify manager installer..."
echo "###################################################################"

# Using $SUDO_USER instead of $USER here because fpm runs the script as sudo
sudo chown $SUDO_USER:$SUDO_USER -R /opt/cloudify-manager-install

echo "###################################################################"
echo "Cloudify installer is ready!"
echo "Edit /opt/cloudify-manager-install/config.yaml, and run cfy_manager install"
echo "###################################################################"