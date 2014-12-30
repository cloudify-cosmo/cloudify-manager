#!/bin/bash -e

fs_mount_path=$(ctx node properties fs_mount_path)

ctx logger info "Unmounting file system on ${fs_mount_path}"
sudo umount ${fs_mount_path}

ctx logger info "Removing ${fs_mount_path} directory"
sudo rmdir ${fs_mount_path}
