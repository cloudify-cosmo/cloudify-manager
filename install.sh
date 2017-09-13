#!/usr/bin/env bash

pushd /opt/cloudify-bootstrap/cloudify-local-bootstrap
    sudo python get-pip.py
    rm get-pip.py
    sudo pip install .
popd