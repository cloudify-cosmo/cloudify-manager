#!/bin/bash

set +e

psql -c "CREATE DATABASE mysite"
psql -c "CREATE USER mysiteuser WITH PASSWORD 'password'"
psql -c "GRANT ALL PRIVILEGES ON DATABASE mysite TO mysiteuser"