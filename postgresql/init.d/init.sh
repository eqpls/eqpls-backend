#!/bin/bash
set -e

# Pre-Initialize ############################################################
psql -v ON_ERROR_STOP=1 --username postgres <<-EOSQL
	CREATE USER $DATABASE_USER PASSWORD '$POSTGRES_PASSWORD' SUPERUSER;
	CREATE ROLE repuser WITH REPLICATION LOGIN PASSWORD '$POSTGRES_PASSWORD';
	COMMIT;
EOSQL

# Initialize ################################################################

# Create Databases
psql -v ON_ERROR_STOP=1 --username postgres <<-EOSQL
	CREATE DATABASE eqpls OWNER $DATABASE_USER;
	CREATE DATABASE keycloak OWNER $DATABASE_USER;
	CREATE DATABASE guacamole OWNER $DATABASE_USER;
	COMMIT;
EOSQL

# Set Database Scheme & Data
if [ -f /init.d/eqpls.sql ]; then
psql -v ON_ERROR_STOP=1 --username postgres --dbname eqpls -f /init.d/eqpls.sql
fi

if [ -f /init.d/keycloak.sql ]; then
psql -v ON_ERROR_STOP=1 --username postgres --dbname keycloak -f /init.d/keycloak.sql
fi

if [ -f /init.d/guacamole.sql ]; then
psql -v ON_ERROR_STOP=1 --username postgres --dbname guacamole -f /init.d/guacamole.sql
fi