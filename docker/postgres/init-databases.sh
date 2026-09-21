#!/bin/bash
set -e

# Automatically provision dedicated databases if they do not exist
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    SELECT 'CREATE DATABASE iceberg_catalog'
    WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'iceberg_catalog')\gexec
    GRANT ALL PRIVILEGES ON DATABASE iceberg_catalog TO $POSTGRES_USER;
EOSQL
