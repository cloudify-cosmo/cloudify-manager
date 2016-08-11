#!/bin/bash

set +e

psql -c "CREATE DATABASE testdb"
psql -c "CREATE USER admin WITH PASSWORD 'apassword'"
psql -c "GRANT ALL PRIVILEGES ON DATABASE testdb TO admin"
