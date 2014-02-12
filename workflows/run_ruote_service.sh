#!/bin/bash --login

############
# This script is used for running the ruote service.
# Optionally switching to required jruby version and running
# The service using rack up.
#
# Parameter 1: Service port.
#

if [ $# -ne 1 ]; then
    echo "Illegal number of arguments - expected <port>"
    exit 1
fi

port=$1

cd ..
cd workflow-service
RACK_ENV=development unicorn -l 0.0.0.0:${port}
