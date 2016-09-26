#!/bin/bash
set -e
ctx download-resource "config/s3cfg_template" "/home/ubuntu/.s3cfg"

SECRET_KEY=$s3_user_key
ACCESS_KEY=$s3_user_id
S3_BUCKET=$s3_bucket


sed -i "s~secret_key = XXX~secret_key = $SECRET_KEY~g" ~/.s3cfg
sed -i "s~access_key = XXX~access_key = $ACCESS_KEY~g" ~/.s3cfg

export DOCKER_HOST=172.20.0.1

set -x

echo creating image tar.gz..
docker save cloudify/centos-manager:7 | gzip > manager.tar.gz
pushd ~/repos/cloudify-manager-blueprints
    git rev-parse HEAD >> ~/image.sha1
popd

echo uploading docker image..
s3cmd put --acl-public manager.tar.gz $S3_BUCKET/docl-manager.tar.gz
s3cmd put --acl-public ~/image.sha1 $S3_BUCKET/docl-manager.sha1
