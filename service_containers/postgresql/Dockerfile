FROM postgres
ADD --chown=postgres:postgres https://cloudify-cicd.s3.amazonaws.com/db-schema/7.0.0.sql /docker-entrypoint-initdb.d/schema.sql
