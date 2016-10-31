#!/bin/bash
set -e
ctx download-resource "config/s3cfg_template" "/home/ubuntu/.s3cfg"


SECRET_KEY=$s3_user_key
ACCESS_KEY=$s3_user_id
S3_BUCKET=$s3_bucket
BUILD=$build

sed -i "s~secret_key = XXX~secret_key = $SECRET_KEY~g" ~/.s3cfg
sed -i "s~access_key = XXX~access_key = $ACCESS_KEY~g" ~/.s3cfg


logs_folder=$(ctx node properties cfy_logs_path)
pushd ${logs_folder/'~'/$HOME}
    tar -zcvf ~/logs.tar.gz *
popd

set -x

s3cmd put --acl-public ~/logs.tar.gz ${S3_BUCKET}/${BUILD}.tar.gz
