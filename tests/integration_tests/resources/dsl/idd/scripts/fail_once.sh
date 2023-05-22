#!/bin/bash

# The purpose of this script is to fail exactly once.
# It checks to see if a "ran" file exists in the deployment directory
# If it does not exist (e.g., first run), then create it and exit
# If it does exist (e.g., second run), then exit 0

WORKDIR=$(ctx local_deployment_workdir)

if [ -f "${WORKDIR}/ran" ]
then
    exit 0
else
    touch "${WORKDIR}/ran"
    exit 1
fi