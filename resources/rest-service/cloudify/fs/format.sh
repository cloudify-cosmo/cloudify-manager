#!/bin/bash -e

partition_number=$(ctx node properties partition_number)
format_after_unmount=$(ctx node properties format_after_unmount)

device_name=$(ctx instance runtime-properties device_name)

if [ -z "${format_after_unmount}" ]; then
    ctx logger info "Erasing disk partition ${device_name}${partition_number}"
    (echo d; echo ${partition_number}; echo w) | sudo fdisk ${device_name}
else
    ctx logger info "Not erasing device since 'format_after_unmount' is set to false"
fi
