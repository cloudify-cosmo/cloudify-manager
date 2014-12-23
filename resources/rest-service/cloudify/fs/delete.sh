#!/bin/bash

use_external_resource=$(ctx node properties use_external_resource)
device_name=$(ctx node properties device_name)
partition_number=$(ctx node properties partition_number)
fs_mount_path=$(ctx node properties fs_mount_path)

ctx logger info "Unmounting file system on ${fs_mount_path}"
sudo umount ${fs_mount_path} || exit $?

ctx logger info "Removing ${fs_mount_path} directory"
sudo rmdir ${fs_mount_path} || exit $?

if [ "$use_external_resource" == "false" ]; then
    ctx logger info "Removing disk partition"
    (echo d; echo ${partition_number}; echo w) | sudo fdisk ${device_name}
fi
