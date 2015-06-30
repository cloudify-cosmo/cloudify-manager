#!/bin/bash -e

# If some operation fails, we should revert all introduced environmental changes
function reentrancy_cleanup {
    if [ $? -eq 0 ]; then # Successful execution, nothing to do
        return
    fi
    ctx logger warning "mount.sh failed, reverting changes introduced by this script."
    if [ $CHOWN_OK ]; then
        ctx logger info "Changing ownership of ${fs_mount_path} back to ${prev_fs_mount_path_owner}"
        sudo chown -R ${prev_fs_mount_path_owner} ${fs_mount_path}
    fi
    if [ $MOUNT_OK ]; then
        ctx logger info "Unmounting ${fs_mount_path}"
        sudo umount ${fs_mount_path}
    fi
}
trap reentrancy_cleanup EXIT

fs_mount_path=$(ctx source node properties fs_mount_path)
filesys=$(ctx source instance runtime-properties filesys)
fs_type=$(ctx source node properties fs_type)

if [ ! -f ${fs_mount_path} ]; then
    sudo mkdir -p ${fs_mount_path}
fi

ctx logger info "Mounting file system ${filesys} on ${fs_mount_path}"
sudo mount ${filesys} ${fs_mount_path}
MOUNT_OK=1

user=$(whoami)
ctx logger info "Changing ownership of ${fs_mount_path} to ${user}"

prev_fs_mount_path_owner=`stat -c %U ${fs_mount_path}`
sudo chown -R ${user} ${fs_mount_path}
CHOWN_OK=1

ctx logger info "Adding mount point ${fs_mount_path} to file system table"
echo ${filesys} ${fs_mount_path} ${fs_type} auto 0 0 | sudo tee --append /etc/fstab > /dev/null