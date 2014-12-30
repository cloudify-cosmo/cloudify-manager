#!/bin/bash -e

fs_mount_path=$(ctx source node properties fs_mount_path)
partition_number=$(ctx source node properties partition_number)
format_after_unmount=$(ctx source node properties format_after_unmount)

device_name=${DEVICE_NAME}

ctx logger info "Unmounting file system on ${fs_mount_path}"
sudo umount ${fs_mount_path}

ctx logger info "Removing ${fs_mount_path} directory"
sudo rmdir ${fs_mount_path}

if [ -z "${format_after_unmount}" ]; then
    ctx logger info "Removing disk partition"
    (echo d; echo ${partition_number}; echo w) | sudo fdisk ${device_name}
fi
