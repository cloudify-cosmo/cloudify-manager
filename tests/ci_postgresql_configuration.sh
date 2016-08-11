#!/bin/bash

set +e

function run_psql() {
    cmd=$1
    echo "Going to run: ${cmd}"
    psql -c "${cmd}"
}

function create_cloudify_user() {
    run_psql "CREATE USER cloudify WITH PASSWORD 'cloudify'"
    run_psql "ALTER USER cloudify CREATEDB"
}

create_cloudify_user

