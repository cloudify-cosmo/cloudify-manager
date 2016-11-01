#!/bin/bash
set -e

# remove /tmp/cloudify-ctx/ from python path. this causes module collision
export PYTHONPATH=''

VENV_PATH=$1
SUITE_RUNNER_PATH=$2
TESTS=$3

export CFY_LOGS_PATH=$4
export JENKINS_JOB=true

echo 'activating venv ' $VENV_PATH
source $VENV_PATH/bin/activate

echo 'running integration tests' $TESTS
python $SUITE_RUNNER_PATH $TESTS
