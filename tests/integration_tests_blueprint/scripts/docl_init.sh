#!/bin/bash
set -e
# remove /tmp/cloudify-ctx/ from python path. this causes module collision
export PYTHONPATH=''

VENV_PATH=$1
BP_PATH=$2
KEY_PATH=$3
SOURCES_ROOT=$4
REBUILD=$5

echo 'activating venv' $VENV_PATH
source $VENV_PATH/bin/activate

docl init --reset --simple-manager-blueprint-path $BP_PATH --ssh-key-path $KEY_PATH --source-root $SOURCES_ROOT --docker-host 172.20.0.1
if [ "${REBUILD,,}" = "true" ]; then
    echo performing docl bootstrap
    docl bootstrap --inputs='ignore_bootstrap_validations=true'| tee /home/ubuntu/bootstrap.out
    docl save-image

else
    echo performing docl pull-image
    docl pull-image --no-progress
fi
