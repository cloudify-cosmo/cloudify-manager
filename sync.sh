#!/usr/bin/env bash

rsync -avz --delete /Users/pavel/Dropbox/Cloudify/local_bs centos@10.239.3.194:/home/centos/local_bs --exclude '*.pyc' --exclude '*.egg-info*'
