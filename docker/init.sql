-- Database initialisation, run once by the postgres container on first boot
-- (only when the data volume is empty).

-- pgvector: required by the pgvector/pgvector image used for the db service.
CREATE EXTENSION IF NOT EXISTS vector;

-- Case-insensitive text and trigram search, used by domain/keyword lookups.
CREATE EXTENSION IF NOT EXISTS pg_trgm;
