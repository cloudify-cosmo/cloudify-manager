#!/bin/bash -e

fs_mount_path=$(ctx source node properties fs_mount_path)

ctx logger info "Unmounting file system on ${fs_mount_path}"
sudo umount ${fs_mount_path}

ctx logger info "Removing ${fs_mount_path} directory"
sudo rmdir ${fs_mount_path} || true

ctx logger info "Removing mount point ${fs_mount_path} from file system table"
sudo sed -i '\?'"$fs_mount_path "'?d' /etc/fstab
