-- The community archive in PostgreSQL.
--
-- One table holds what three components hold today: the vectors Qdrant keeps,
-- the civic metadata the retriever filters in Python, and the keyword index
-- BM25 rebuilds in memory on every process start. ROADMAP.md section 2.3 makes
-- the argument; this file is the shape it takes.
--
-- The dimension is a template token rather than a literal because a pgvector
-- column has a fixed width and changing embedding models is a re-index, not a
-- config flip. stores/migrate.py substitutes it. To run this by hand:
--
--     sed 's/{{VECTOR_DIMENSION}}/384/' stores/schema.sql | psql "$COMMUNITY_DB_URL"
--
-- 384 is all-MiniLM-L6-v2, the default. 1024 is BAAI/bge-m3. The table in
-- vector_store.EMBEDDING_MODELS is the authority for the rest.
--
-- Every statement is IF NOT EXISTS so an operator can re-run the whole file
-- after a failed migration without dropping a town's public record.

CREATE EXTENSION IF NOT EXISTS vector;


CREATE TABLE IF NOT EXISTS chunks (
    -- Multi-tenancy. Every row carries its community, every query filters on
    -- it, and the optional row-level security policy at the bottom of this
    -- file turns that convention into something the database enforces.
    project_id      text NOT NULL,
    id              text NOT NULL,

    -- "text" and "date" are quoted because both are also type names. The
    -- columns keep the payload's own key names so moving a row to a payload
    -- and back needs no renaming step, and a misspelling in either direction
    -- fails loudly instead of silently dropping civic metadata.
    "text"          text NOT NULL,
    embedding       vector({{VECTOR_DIMENSION}}),

    -- Provenance
    source          text NOT NULL DEFAULT '',
    source_type     text NOT NULL DEFAULT 'unknown',
    url             text NOT NULL DEFAULT '',
    title           text NOT NULL DEFAULT '',

    -- Civic identity
    community       text NOT NULL DEFAULT '',
    body            text NOT NULL DEFAULT '',
    department      text NOT NULL DEFAULT '',

    -- Meetings
    meeting_date    date,
    agenda_item     text NOT NULL DEFAULT '',
    speaker         text NOT NULL DEFAULT '',
    speaker_role    text NOT NULL DEFAULT '',
    start_time      double precision,   -- seconds into the recording
    end_time        double precision,
    video_url       text NOT NULL DEFAULT '',

    -- Documents
    document_type   text NOT NULL DEFAULT '',
    page            integer,
    section         text NOT NULL DEFAULT '',
    effective_date  date,

    -- Discussion, a proposal, or adopted text. The distinction Principle 16
    -- depends on, recorded at ingestion rather than inferred by the model at
    -- answer time, along with what the ingestion path thought of its own guess.
    status            text NOT NULL DEFAULT 'unknown',
    status_confidence double precision,
    vote_taken        boolean NOT NULL DEFAULT false,
    vote_outcome      text NOT NULL DEFAULT '',   -- passed | failed | tabled | none
    vote_tally        text NOT NULL DEFAULT '',   -- "4-1", "unanimous"
    status_evidence   text NOT NULL DEFAULT '',   -- the words that decided the status

    -- Identifiers keyword search handles better than embeddings
    docket_number   text NOT NULL DEFAULT '',
    project_name    text NOT NULL DEFAULT '',
    address         text NOT NULL DEFAULT '',
    geography       text NOT NULL DEFAULT '',

    -- Operations
    collection_method text NOT NULL DEFAULT '',
    ingested_at     date,
    "date"          date,               -- the legacy generic date in CivicChunk

    -- Whatever a collector recorded that has no column of its own. Keeping it
    -- means an ingestion path can add a field without a migration, and nothing
    -- a community already collected is thrown away on the way in.
    payload         jsonb NOT NULL DEFAULT '{}'::jsonb,

    -- The date that matters for this record, whatever its type. CivicChunk
    -- computes this in Python as `record_date`; a stored generated column lets
    -- a date-range filter use an index instead of three COALESCEd comparisons.
    record_date     date GENERATED ALWAYS AS
                        (COALESCE(meeting_date, effective_date, "date")) STORED,

    -- The keyword half of hybrid retrieval, maintained by the database.
    --
    -- The configuration is spelled out as 'english' rather than left to
    -- default_text_search_config because a generated column needs an immutable
    -- expression, and the one-argument to_tsvector() is only stable. Queries
    -- must name the same configuration or they will not match this index.
    --
    -- Weights carry the judgment: the passage itself is the evidence (A), a
    -- title narrows a document search (B), and the civic identifiers are
    -- included (C) so "Article 8.4" and "24-105" match even when the number
    -- appears only in the section or docket column.
    tsv             tsvector GENERATED ALWAYS AS (
                        setweight(to_tsvector('english', coalesce("text", '')), 'A') ||
                        setweight(to_tsvector('english', coalesce(title, '')), 'B') ||
                        setweight(to_tsvector('english',
                            coalesce(section, '') || ' ' ||
                            coalesce(docket_number, '') || ' ' ||
                            coalesce(agenda_item, '') || ' ' ||
                            coalesce(speaker, '')), 'C')
                    ) STORED,

    -- The id is deterministic per chunk, so re-ingesting a source updates a row
    -- rather than duplicating it. Two communities may legitimately hold the
    -- same id, which is why the key is the pair.
    PRIMARY KEY (project_id, id)
);

-- Columns that arrived after the first release. CREATE TABLE IF NOT EXISTS
-- leaves a table that already exists exactly as it was, so re-running this file
-- on an older deployment only picks up a new column if the column asks.
ALTER TABLE chunks ADD COLUMN IF NOT EXISTS status_evidence text NOT NULL DEFAULT '';


-- Dense retrieval. HNSW rather than IVFFlat: it needs no training pass, so a
-- community that ingests its archive over weeks never has an index built
-- against a corpus a tenth its eventual size.
--
-- vector_cosine_ops matches the Qdrant collections this replaces, which were
-- created with Distance.COSINE. Using a different operator class here would
-- silently change what "most similar" means after a migration.
CREATE INDEX IF NOT EXISTS chunks_embedding_hnsw
    ON chunks USING hnsw (embedding vector_cosine_ops);

-- Keyword retrieval. This index is the reason the app stops being pinned to
-- one instance: it lives on disk, every instance shares it, and it is updated
-- by the write rather than rebuilt on the next cold start.
CREATE INDEX IF NOT EXISTS chunks_tsv_gin
    ON chunks USING gin (tsv);

-- The civic filters. Each is prefixed with project_id because no query ever
-- crosses communities, so an index that does not start there is half wasted.
CREATE INDEX IF NOT EXISTS chunks_project_source_type
    ON chunks (project_id, source_type);
CREATE INDEX IF NOT EXISTS chunks_project_body
    ON chunks (project_id, body);
CREATE INDEX IF NOT EXISTS chunks_project_meeting_date
    ON chunks (project_id, meeting_date);

-- "What did the Planning Board decide in 2019" filters on the record date, not
-- the meeting date, because a bylaw has an effective date and no meeting.
CREATE INDEX IF NOT EXISTS chunks_project_record_date
    ON chunks (project_id, record_date);

-- Re-ingesting a source deletes its rows first. Without this that is a scan of
-- the whole community's archive.
CREATE INDEX IF NOT EXISTS chunks_project_source
    ON chunks (project_id, source);


-- --------------------------------------------------------------------------
-- Row-level security: optional, and off by default.
--
-- Every query this application issues already carries `WHERE project_id = ...`.
-- That is enough for one community on its own database, and it is the whole
-- protection for many communities sharing one. RLS makes the database enforce
-- what the application currently promises, so a missing WHERE clause in code
-- written next year returns nothing rather than another town's record.
--
-- It is commented out because turning it on changes who can read what, which
-- is a decision an operator should make deliberately rather than inherit from
-- a schema file. Enable it when more than one community shares a database.
--
-- The application would then set the tenant once per connection:
--
--     SET LOCAL civic.project_id = 'brookline-ma';
--
-- and the role it connects as must not be the table owner or a superuser,
-- because both bypass RLS by default.
--
--   ALTER TABLE chunks ENABLE ROW LEVEL SECURITY;
--   ALTER TABLE chunks FORCE ROW LEVEL SECURITY;
--
--   CREATE POLICY chunks_tenant_read ON chunks
--       FOR SELECT
--       USING (project_id = current_setting('civic.project_id', true));
--
--   CREATE POLICY chunks_tenant_write ON chunks
--       FOR ALL
--       USING (project_id = current_setting('civic.project_id', true))
--       WITH CHECK (project_id = current_setting('civic.project_id', true));
--
--   -- The migration and the sync jobs need to write across communities.
--   -- Give them a role that is exempt rather than widening the policy:
--   --   CREATE ROLE civic_migrator BYPASSRLS;
-- --------------------------------------------------------------------------
