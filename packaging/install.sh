#!/usr/bin/env bash

echo "###################################################################"
echo "Installing cloudify manager installer..."
echo "###################################################################"

# Using $SUDO_USER instead of $USER here because fpm runs the script as sudo
# and needs access to the config file as the user
sudo chown $SUDO_USER:$SUDO_USER /opt/cloudify/config.yaml

echo "###################################################################"
echo "Cloudify installer is ready!"
echo "Edit /opt/cloudify/config.yaml, and run cfy_manager install"
echo "###################################################################"
