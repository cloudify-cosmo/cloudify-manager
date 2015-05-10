#!/bin/bash -e

fs_mount_path=$(ctx source node properties fs_mount_path)
filesys=$(ctx source instance runtime-properties filesys)
fs_type=$(ctx source node properties fs_type)

ctx logger info "HERE0"
if [ ! -f ${fs_mount_path} ]; then
    sudo mkdir -p ${fs_mount_path}
    ctx logger info "HERE"
elif which docker; then
    ctx logger info "HERE2"
    docker_back=/tmp/docker_back
    sudo mkdir ${docker_back}
    sudo service docker stop
    ctx logger info "Backing up existing docker files on ${fs_mount_path} to ${docker_back}"
    sudo cp -a ${fs_mount_path}/. ${docker_back}
fi

ctx logger info "Mounting file system ${filesys} on ${fs_mount_path}"
sudo mount ${filesys} ${fs_mount_path}
if [ ! -z ${docker_back} ]; then
    ctx logger info "Restoring docker files from local backup ${docker_back} to ${fs_mount_path}"
    sudo cp -a ${docker_back}/. ${fs_mount_path}
fi

user=$(whoami)
ctx logger info "Changing ownership of ${fs_mount_path} to ${user}"
sudo chown -R ${user} ${fs_mount_path}

ctx logger info "Adding mount point ${fs_mount_path} to file system table"
echo ${filesys} ${fs_mount_path} ${fs_type} auto 0 0 | sudo tee --append /etc/fstab > /dev/null
