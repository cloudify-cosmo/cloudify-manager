#!/bin/bash -e

fs_mount_path=$(ctx source node properties fs_mount_path)
filesys=$(ctx source instance runtime-properties filesys)
fs_type=$(ctx source node properties fs_type)
recovery_enabled=$(ctx source instance runtime-properties recovery_enabled)

if [ ! -d ${fs_mount_path} ]; then
    sudo mkdir -p ${fs_mount_path}
elif which docker; then
    sudo service docker stop
    if [ -z ${recovery_enabled} ]; then
        docker_back=/tmp/docker_back
        sudo mkdir -p ${docker_back}
        sudo service docker stop
        ctx logger info "Backing up existing docker files on ${fs_mount_path} to ${docker_back}"
        sudo cp -a ${fs_mount_path}/. ${docker_back}
    fi
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

if which docker; then
    ctx logger info "Starting docker service"
    sudo service docker restart
fi

ctx logger info "Marking this instance as mounted"
ctx source instance runtime-properties recovery_enabled "True"
