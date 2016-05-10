#!/bin/bash -e

use_external_resource=$(ctx node properties use_external_resource)
fs_type=$(ctx node properties fs_type)
filesys=$(ctx instance runtime-properties filesys)

created=$(ctx instance runtime-properties created || true)

if [[ -z "${use_external_resource}" && -z "${created}" ]]; then
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

    ctx logger info "Creating ${fs_type} file system using ${mkfs_executable}"
    sudo ${mkfs_executable} ${filesys}
    ctx logger info "Marking this instance as created"
    ctx instance runtime-properties created "True"
else
    ctx logger info "Not making a filesystem since is already created"
fi
