#!/bin/bash -e

fs_mount_path=$(ctx source node properties fs_mount_path)
filesys=$(ctx source instance runtime-properties filesys)
fs_type=$(ctx source node properties fs_type)
ever_mounted=$(ctx source instance runtime-properties ever_mounted || true)

ctx logger info "Checking whether docker is installed"
set +e
which docker
docker_installed=$?
set -e

if [ ! -d ${fs_mount_path} ]; then
    sudo mkdir -p ${fs_mount_path}
elif [ ${docker_installed} == 0 ]; then
    ctx logger info "Stopping docker service"
    sudo service docker stop
    if [ -z ${ever_mounted} ]; then
        docker_files=/tmp/cfy_docker_files
        sudo mkdir -p ${docker_files}
        ctx logger info "Backing up existing docker files on ${fs_mount_path} to ${docker_files}"
        sudo cp -a ${fs_mount_path}/. ${docker_files}
    fi
fi

ctx logger info "Mounting file system ${filesys} on ${fs_mount_path}"
sudo mount ${filesys} ${fs_mount_path}

if [ ! -z ${docker_files} ]; then
    ctx logger info "Restoring docker files from local backup ${docker_files} to ${fs_mount_path}"
    sudo cp -a ${docker_files}/. ${fs_mount_path}
    sudo rm -rf ${docker_files}
fi

ctx logger info "Adding mount point ${fs_mount_path} to file system table"
echo ${filesys} ${fs_mount_path} ${fs_type} auto 0 0 | sudo tee --append /etc/fstab > /dev/null

if [ ${docker_installed} == 0 ]; then
    ctx logger info "Starting docker service"
    sudo service docker start
fi

ctx logger info "Marking this instance as mounted"
ctx source instance runtime-properties ever_mounted "True"
