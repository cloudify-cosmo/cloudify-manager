#!/bin/bash

set -e

if [ $# -lt 3 ]; then
    echo "Missing arguments."
    echo "Usage: $0 db_name username password"
    exit
fi

db_name=$1
stage_db_name="stage"
composer_db_name="composer"
user=$2
password=$3

function run_psql() {
    cmd=$1
    echo "Going to run: ${cmd}"
    psql -c "${cmd}"
}

function clean_database_and_user() {
    db_name=$1
    user=$2
    run_psql "DROP DATABASE IF EXISTS $db_name;"
    run_psql "DROP DATABASE IF EXISTS $stage_db_name;"
    run_psql "DROP DATABASE IF EXISTS $composer_db_name;"
    run_psql "DROP USER IF EXISTS $user;"
}

function create_database() {
    db_name=$1
    run_psql "CREATE DATABASE $db_name"
}

function create_admin_user() {
    db=$1
    user=$2
    password=$3
    run_psql "CREATE USER $user WITH PASSWORD '$password';"
    run_psql "GRANT ALL PRIVILEGES ON DATABASE $db TO $user;"
    run_psql "ALTER USER $user CREATEDB;"
    run_psql "ALTER DATABASE $db OWNER TO $user;"
}

function create_stage_database() {
    db=$1
    user=$2
    run_psql "CREATE DATABASE $db"
    run_psql "GRANT ALL PRIVILEGES ON DATABASE $db TO $user;"
    run_psql "ALTER DATABASE $db OWNER TO $user;"
}

function create_composer_database() {
    db=$1
    user=$2
    run_psql "CREATE DATABASE $db"
    run_psql "GRANT ALL PRIVILEGES ON DATABASE $db TO $user;"
    run_psql "ALTER DATABASE $db OWNER TO $user;"
}

clean_database_and_user ${db_name} ${user}
create_database ${db_name}
create_admin_user ${db_name} ${user} ${password}
create_stage_database ${stage_db_name} ${user}
create_composer_database ${composer_db_name} ${user}