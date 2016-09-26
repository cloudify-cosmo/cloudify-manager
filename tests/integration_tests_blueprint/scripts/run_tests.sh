#!/bin/bash
set -e

# remove /tmp/cloudify-ctx/ from python path. this causes module collision
export PYTHONPATH=''

VENV_PATH=$1
SUITE_RUNNER_PATH=$2
TESTS=$3

echo 'activating venv ' $VENV_PATH
source $VENV_PATH/bin/activate

#security is enabled by default
export CLOUDIFY_USERNAME=admin
export CLOUDIFY_PASSWORD=admin

echo 'running integration tests ' $TESTS
python $SUITE_RUNNER_PATH $TESTS
