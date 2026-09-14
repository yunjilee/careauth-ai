#!/bin/bash
# Creates separate databases and credentials for HAPI and the application, as
# required by the design: the application integrates through FHIR REST and never
# reads HAPI's internal tables.
set -euo pipefail

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname postgres <<-EOSQL
    CREATE ROLE ${HAPI_DB_USER} LOGIN PASSWORD '${HAPI_DB_PASSWORD}';
    CREATE DATABASE hapi OWNER ${HAPI_DB_USER};

    CREATE ROLE ${APP_DB_USER} LOGIN PASSWORD '${APP_DB_PASSWORD}';
    CREATE DATABASE careauth OWNER ${APP_DB_USER};

    REVOKE CONNECT ON DATABASE hapi FROM ${APP_DB_USER};
    REVOKE CONNECT ON DATABASE careauth FROM ${HAPI_DB_USER};
EOSQL

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname careauth <<-EOSQL
    CREATE EXTENSION IF NOT EXISTS vector;
    CREATE EXTENSION IF NOT EXISTS pg_trgm;
EOSQL
