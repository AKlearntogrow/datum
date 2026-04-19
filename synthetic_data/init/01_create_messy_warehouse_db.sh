#!/bin/bash
set -e

# Create the messy_warehouse database, owned by the same 'datum' user.
# This runs only when the Postgres data volume is fresh.

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" <<-EOSQL
    CREATE DATABASE messy_warehouse OWNER $POSTGRES_USER;
EOSQL

echo "Created messy_warehouse database."
