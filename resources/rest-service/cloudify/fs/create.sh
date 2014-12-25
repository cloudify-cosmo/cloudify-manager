#!/bin/bash

use_external_resource=$(ctx node properties use_external_resource)
device_name=$(ctx node properties device_name)
partition_type=$(ctx node properties partition_type)
partition_number=$(ctx node properties partition_number)
fs_type=$(ctx node properties fs_type)
fs_mount_path=$(ctx node properties fs_mount_path)

ctx logger info "use_external_resource = ${use_external_resource}"
ctx logger info "device_name = ${device_name}"
ctx logger info "partition_type = ${partition_type}"
ctx logger info "partition_number = ${partition_number}"
ctx logger info "fs_type = ${fs_type}"
ctx logger info "fs_mount_path = ${fs_mount_path}"

if [ "${use_external_resource}" == "false" ]; then
    mkfs_executable=''
    case ${fs_type} in
        ext2 | ext3 | ext4 | fat | ntfs )
         mkfs_executable='mkfs.'${fs_type};;
        swap )
         mkfs_executable='mkswap';;
        * )
         ctx logger error "File system type is not supported."
         exit 1;;
    esac
    
    ctx logger info "Creating disk partition"
    (echo n; echo p; echo ${partition_number}; echo ; echo ; echo t; echo ${partition_type}; echo w) | sudo fdisk ${device_name}
    
    ctx logger info "Creating ${fs_type} file system using ${mkfs_executable}"
    sudo ${mkfs_executable} ${device_name}${partition_number} || exit $?
fi

if [ ! -f ${fs_mount_path} ]; then
    sudo mkdir -p ${fs_mount_path} || exit $?
fi

ctx logger info "Mounting file system on ${fs_mount_path}"
sudo mount ${device_name}${partition_number} ${fs_mount_path} || exit $?
