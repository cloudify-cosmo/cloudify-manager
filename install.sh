#!/usr/bin/env bash

pushd /opt/cloudify-bootstrap
    sudo python get-pip.py
    rm -f get-pip.py
    sudo pip install ./cloudify-local-bootstrap
popd