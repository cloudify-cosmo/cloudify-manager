#!/bin/bash --login

############
# This script is used for running the ruote service.
# Optionally switching to required jruby version and running
# The service using rack up.
#
# Parameter 1: Whether to switch to jruby-1.7.3 using rvm.
# Parameter 2: Service port.
#

export JRUBY_OPTS=-J-XX:MaxPermSize=196M

if [ $# -ne 2 ]; then
    echo "Illegal number of arguments - expected <use_rvm|true/false> <port>"
    exit 1
fi

use_rvm=$1
port=$2

if [ "$use_rvm" == "true" ]; then
    rvm use jruby-1.7.3
fi
cd ..
cd workflow-service
RACK_ENV=development rackup -p $port
