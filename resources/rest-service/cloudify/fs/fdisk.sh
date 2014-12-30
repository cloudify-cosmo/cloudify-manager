#!/bin/bash -e

use_external_resource=$(ctx source node properties use_external_resource)
partition_type=$(ctx source node properties partition_type)
partition_number=$(ctx source node properties partition_number)
fs_type=$(ctx source node properties fs_type)

device_name=${DEVICE_NAME}

if [ -z "${use_external_resource}" ]; then

    ctx logger info "Creating disk partition"
    (echo n; echo p; echo ${partition_number}; echo ; echo ; echo t; echo ${partition_type}; echo w) | sudo fdisk ${device_name}

fi

# Set this runtime property on the source (the filesystem)
# its needed by subsequent scripts
ctx source instance runtime-properties filesys ${device_name}${partition_number}