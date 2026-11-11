-- Run once as the postgres superuser (see README step "PostgreSQL setup").
-- Change the password below, and use the same one in backend/.env
CREATE USER eventhub WITH PASSWORD 'CHANGE_ME';
CREATE DATABASE eventhub OWNER eventhub;
CREATE DATABASE eventhub_test OWNER eventhub;
