#!/bin/bash --login

############
# This script is used for running the ruote service.
# Optionally switching to required jruby version and running
# The service using rack up.
#
# Parameter 1: Whether to switch to ruby-2.1.0 using rvm.
# Parameter 2: Service port.
#

if [ $# -ne 2 ]; then
    echo "Illegal number of arguments - expected <use_rvm|true/false> <port>"
    exit 1
fi

use_rvm=$1
port=$2

if [ "$use_rvm" == "true" ]; then
    rvm use ruby-2.1.0
fi
cd ..
cd workflow-service
RACK_ENV=development unicorn -l 0.0.0.0:${port}
