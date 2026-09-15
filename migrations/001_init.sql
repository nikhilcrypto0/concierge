-- Knowledge base, business data, human approvals, action audit log, and token ledger.
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE kb_chunks (
    id            TEXT PRIMARY KEY,               -- "<doc_slug>#<n>"
    doc_slug      TEXT NOT NULL,
    doc_title     TEXT NOT NULL,
    heading       TEXT NOT NULL,
    content       TEXT NOT NULL,
    content_hash  TEXT NOT NULL,
    embedding     vector(384) NOT NULL,
    tsv           tsvector GENERATED ALWAYS AS (
                      setweight(to_tsvector('english', doc_title || ' ' || heading), 'A') ||
                      setweight(to_tsvector('english', content), 'B')
                  ) STORED,
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX kb_chunks_embedding_idx ON kb_chunks USING hnsw (embedding vector_cosine_ops);
CREATE INDEX kb_chunks_tsv_idx ON kb_chunks USING gin (tsv);

CREATE TABLE bookings (
    reference       TEXT PRIMARY KEY,             -- "BK-1042"
    customer_email  TEXT NOT NULL,
    service         TEXT NOT NULL,
    scheduled_for   TIMESTAMPTZ NOT NULL,
    amount_cents    INTEGER NOT NULL CHECK (amount_cents >= 0),
    status          TEXT NOT NULL CHECK (status IN ('scheduled', 'completed', 'cancelled')),
    refunded_cents  INTEGER NOT NULL DEFAULT 0 CHECK (refunded_cents >= 0),
    CHECK (refunded_cents <= amount_cents)
);
CREATE INDEX bookings_customer_idx ON bookings (customer_email);

CREATE TABLE conversations (
    id              UUID PRIMARY KEY,
    customer_email  TEXT NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE approval_requests (
    id                 UUID PRIMARY KEY,
    conversation_id    UUID NOT NULL REFERENCES conversations (id),
    booking_reference  TEXT NOT NULL REFERENCES bookings (reference),
    action             TEXT NOT NULL CHECK (action IN ('refund')),
    amount_cents       INTEGER NOT NULL CHECK (amount_cents > 0),
    policy_reason      TEXT NOT NULL,
    status             TEXT NOT NULL DEFAULT 'pending'
                           CHECK (status IN ('pending', 'approved', 'rejected')),
    reviewer           TEXT,
    review_note        TEXT,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    decided_at         TIMESTAMPTZ
);
-- At most one open request per conversation: a paused graph can only wait on one decision.
CREATE UNIQUE INDEX approval_one_pending_per_conversation
    ON approval_requests (conversation_id) WHERE status = 'pending';

CREATE TABLE actions (
    idempotency_key    TEXT PRIMARY KEY,           -- replays of the same step cannot double-refund
    approval_id        UUID NOT NULL REFERENCES approval_requests (id),
    booking_reference  TEXT NOT NULL REFERENCES bookings (reference),
    action             TEXT NOT NULL,
    amount_cents       INTEGER NOT NULL,
    executed_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE llm_usage (
    id               BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    conversation_id  UUID NOT NULL,
    step             TEXT NOT NULL,
    model            TEXT NOT NULL,
    input_tokens     INTEGER NOT NULL,
    output_tokens    INTEGER NOT NULL,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX llm_usage_conversation_idx ON llm_usage (conversation_id);
CREATE INDEX llm_usage_created_idx ON llm_usage (created_at);
