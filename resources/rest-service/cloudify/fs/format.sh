#!/bin/bash -e

partition_number=$(ctx source node properties partition_number)
format_after_unmount=$(ctx source node properties format_after_unmount)

device_name=$(ctx source instance runtime-properties device_name)

if [ -z "${format_after_unmount}" ]; then
    ctx logger info "Removing disk partition"
    (echo d; echo ${partition_number}; echo w) | sudo fdisk ${device_name}
fi
