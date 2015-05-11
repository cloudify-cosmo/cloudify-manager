#!/bin/bash -e

fs_mount_path=$(ctx source node properties fs_mount_path)
filesys=$(ctx source instance runtime-properties filesys)
fs_type=$(ctx source node properties fs_type)
echo HERE1
mounted_once=$(ctx source instance runtime-properties mounted_once)
echo HERE2
if [ ! -d ${fs_mount_path} ]; then
    echo HERE3
    sudo mkdir -p ${fs_mount_path}
elif which docker && [ -z ${mounted_once} ]; then
    echo HERE4
    docker_back=/tmp/docker_back
    sudo mkdir -p ${docker_back}
    sudo service docker stop
    ctx logger info "Backing up existing docker files on ${fs_mount_path} to ${docker_back}"
    sudo cp -a ${fs_mount_path}/. ${docker_back}
fi

ctx logger info "Mounting file system ${filesys} on ${fs_mount_path}"
sudo mount ${filesys} ${fs_mount_path}
if [ ! -z ${docker_back} ]; then
    ctx logger info "Restoring docker files from local backup ${docker_back} to ${fs_mount_path}"
    sudo cp -a ${docker_back}/. ${fs_mount_path}
    sudo rm -rf ${docker_back}
fi

user=$(whoami)
ctx logger info "Changing ownership of ${fs_mount_path} to ${user}"
sudo chown -R ${user} ${fs_mount_path}

ctx logger info "Adding mount point ${fs_mount_path} to file system table"
echo ${filesys} ${fs_mount_path} ${fs_type} auto 0 0 | sudo tee --append /etc/fstab > /dev/null
echo HERE5
ctx logger info "Marking this instance as mounted"
ctx instance source instance runtime-properties mounted_once "True"
