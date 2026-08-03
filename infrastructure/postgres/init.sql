-- ╔══════════════════════════════════════════════════════════════════════════╗
-- ║  VIDHYA BOT PLATFORM v3 — Database Initialization                      ║
-- ║  This script runs ONCE on first database creation (empty volume).       ║
-- ║  Subsequent schema changes should use Alembic migrations.               ║
-- ╚══════════════════════════════════════════════════════════════════════════╝

-- ═══════════════════════════════════════════════════════════════════
-- EXTENSIONS
-- ═══════════════════════════════════════════════════════════════════

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "vector";       -- pgvector for RAG embeddings
CREATE EXTENSION IF NOT EXISTS "pg_trgm";      -- trigram for fuzzy text search


-- ═══════════════════════════════════════════════════════════════════
-- 1. USERS
-- ═══════════════════════════════════════════════════════════════════

CREATE TABLE users (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    telegram_id         BIGINT UNIQUE NOT NULL,
    telegram_username   VARCHAR(100),
    first_name          VARCHAR(100) NOT NULL,
    last_name           VARCHAR(100),
    photo_url           TEXT,
    language_code       VARCHAR(10) DEFAULT 'en',
    is_active           BOOLEAN DEFAULT TRUE,
    is_banned           BOOLEAN DEFAULT FALSE,
    ban_reason           TEXT,
    last_login_at       TIMESTAMPTZ,
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_users_telegram_id ON users(telegram_id);
CREATE INDEX idx_users_active ON users(is_active) WHERE is_active = TRUE;


-- ═══════════════════════════════════════════════════════════════════
-- 2. ADMINS
-- ═══════════════════════════════════════════════════════════════════

CREATE TABLE admins (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username            VARCHAR(50) UNIQUE NOT NULL,
    email               VARCHAR(255) UNIQUE,            -- Admin email for notifications
    password_hash       TEXT NOT NULL,          -- Argon2id
    role                VARCHAR(20) DEFAULT 'admin',  -- superadmin | admin | viewer
    totp_secret         VARCHAR(64),
    totp_enabled        BOOLEAN DEFAULT FALSE,
    is_active           BOOLEAN DEFAULT TRUE,
    failed_login_count  INTEGER DEFAULT 0,
    locked_until        TIMESTAMPTZ,
    last_login_at       TIMESTAMPTZ,
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW()
);


-- ═══════════════════════════════════════════════════════════════════
-- 3. SESSIONS
-- ═══════════════════════════════════════════════════════════════════

CREATE TABLE sessions (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    session_token       VARCHAR(255) UNIQUE NOT NULL,
    device_info         JSONB,
    ip_address          INET,
    is_active           BOOLEAN DEFAULT TRUE,
    expires_at          TIMESTAMPTZ NOT NULL,
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    last_accessed_at    TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_sessions_user ON sessions(user_id);
CREATE INDEX idx_sessions_token ON sessions(session_token);
CREATE INDEX idx_sessions_expires ON sessions(expires_at);


-- ═══════════════════════════════════════════════════════════════════
-- 4. PLANS — Full Control Layer
-- ═══════════════════════════════════════════════════════════════════

CREATE TABLE plans (
    id                          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name                        VARCHAR(50) UNIQUE NOT NULL,
    display_name                VARCHAR(100) NOT NULL,
    description                 TEXT,
    price_inr                   INTEGER NOT NULL DEFAULT 0,
    validity_days               INTEGER NOT NULL DEFAULT 30,
    is_active                   BOOLEAN DEFAULT TRUE,

    -- Message Quotas
    messages_per_day            INTEGER NOT NULL DEFAULT 5,
    messages_per_month          INTEGER NOT NULL DEFAULT 50,

    -- Conversation Limits
    max_conversations           INTEGER NOT NULL DEFAULT 3,
    max_active_conversations    INTEGER NOT NULL DEFAULT 1,
    conversation_timeout_min    INTEGER NOT NULL DEFAULT 30,

    -- Context / Token Controls
    max_context_messages        INTEGER NOT NULL DEFAULT 5,
    max_context_tokens          INTEGER NOT NULL DEFAULT 2000,
    max_response_tokens         INTEGER NOT NULL DEFAULT 512,

    -- Memory Controls
    memory_retention_days       INTEGER NOT NULL DEFAULT 7,
    summary_frequency           INTEGER NOT NULL DEFAULT 10,
    long_term_memory_enabled    BOOLEAN DEFAULT FALSE,

    -- Feature Flags (JSONB for extensibility)
    features                    JSONB DEFAULT '{
        "rag_enabled": true,
        "streaming_enabled": true,
        "history_export": false,
        "priority_queue": false,
        "subject_filter": false,
        "mcq_mode": false
    }'::jsonb,

    created_at                  TIMESTAMPTZ DEFAULT NOW(),
    updated_at                  TIMESTAMPTZ DEFAULT NOW()
);


-- ═══════════════════════════════════════════════════════════════════
-- 5. PAYMENTS
-- ═══════════════════════════════════════════════════════════════════

CREATE TABLE payments (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    plan_id             UUID NOT NULL REFERENCES plans(id),

    -- PhonePe fields
    merchant_txn_id     VARCHAR(100) UNIQUE NOT NULL,
    phonepe_txn_id      VARCHAR(100),
    amount_inr          INTEGER NOT NULL,           -- in paise (₹99 = 9900)
    currency            VARCHAR(10) DEFAULT 'INR',

    status              VARCHAR(20) DEFAULT 'initiated',
                        -- initiated | pending | success | failed | refunded

    payment_method      VARCHAR(50),                -- UPI, CARD, etc.
    payment_instrument  JSONB,                      -- instrument details
    response_data       JSONB,                      -- full PhonePe response

    initiated_at        TIMESTAMPTZ DEFAULT NOW(),
    completed_at        TIMESTAMPTZ,
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_payments_user ON payments(user_id);
CREATE INDEX idx_payments_merchant_txn ON payments(merchant_txn_id);
CREATE INDEX idx_payments_status ON payments(status);


-- ═══════════════════════════════════════════════════════════════════
-- 6. USER SUBSCRIPTIONS
-- ═══════════════════════════════════════════════════════════════════

CREATE TABLE user_subscriptions (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id                 UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    plan_id                 UUID NOT NULL REFERENCES plans(id),
    payment_id              UUID REFERENCES payments(id),

    status                  VARCHAR(20) DEFAULT 'active',
                            -- active | expired | cancelled | paused

    started_at              TIMESTAMPTZ DEFAULT NOW(),
    expires_at              TIMESTAMPTZ,

    -- Snapshot of plan limits at subscription time (immutable after purchase)
    plan_snapshot           JSONB NOT NULL,

    -- Lifetime usage counters (persisted to DB)
    total_messages_used     INTEGER DEFAULT 0,
    total_tokens_consumed   BIGINT DEFAULT 0,
    total_conversations     INTEGER DEFAULT 0,

    created_at              TIMESTAMPTZ DEFAULT NOW(),
    updated_at              TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_subs_user ON user_subscriptions(user_id);
CREATE INDEX idx_subs_status ON user_subscriptions(user_id, status);
-- Partial unique index: only one active subscription per user
CREATE UNIQUE INDEX idx_subs_user_active ON user_subscriptions(user_id) WHERE status = 'active';


-- ═══════════════════════════════════════════════════════════════════
-- 7. USAGE TRACKING
-- ═══════════════════════════════════════════════════════════════════

CREATE TABLE usage_tracking (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id                 UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    subscription_id         UUID REFERENCES user_subscriptions(id),

    period_type             VARCHAR(10) NOT NULL,       -- 'daily' | 'monthly'
    period_date             DATE NOT NULL,

    messages_used           INTEGER DEFAULT 0,
    tokens_input            BIGINT DEFAULT 0,
    tokens_output           BIGINT DEFAULT 0,
    conversations_created   INTEGER DEFAULT 0,

    created_at              TIMESTAMPTZ DEFAULT NOW(),
    updated_at              TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE(user_id, period_type, period_date)
);

CREATE INDEX idx_usage_user_period ON usage_tracking(user_id, period_type, period_date);


-- ═══════════════════════════════════════════════════════════════════
-- 8. CONVERSATIONS
-- ═══════════════════════════════════════════════════════════════════

CREATE TABLE conversations (
    id                          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id                     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    subscription_id             UUID REFERENCES user_subscriptions(id),

    title                       VARCHAR(255),
    status                      VARCHAR(20) DEFAULT 'active',
                                -- active | closed | timeout | limit_exceeded | archived

    -- Plan limits snapshot (captured when conversation starts)
    max_context_messages        INTEGER NOT NULL,
    max_context_tokens          INTEGER NOT NULL,
    conversation_timeout_min    INTEGER NOT NULL,
    memory_retention_days       INTEGER NOT NULL,

    -- Context tracking
    total_messages              INTEGER DEFAULT 0,
    total_tokens_used           BIGINT DEFAULT 0,

    -- Summary support
    summary_text                TEXT,
    last_summary_at             TIMESTAMPTZ,
    messages_since_summary      INTEGER DEFAULT 0,

    -- Timestamps
    started_at                  TIMESTAMPTZ DEFAULT NOW(),
    last_activity_at            TIMESTAMPTZ DEFAULT NOW(),
    closed_at                   TIMESTAMPTZ,
    auto_close_reason           VARCHAR(100),

    created_at                  TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_conv_user_status ON conversations(user_id, status);
CREATE INDEX idx_conv_last_activity ON conversations(last_activity_at);
CREATE INDEX idx_conv_active ON conversations(user_id, status) WHERE status = 'active';


-- ═══════════════════════════════════════════════════════════════════
-- 9. MESSAGES
-- ═══════════════════════════════════════════════════════════════════

CREATE TABLE messages (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id     UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    user_id             UUID NOT NULL REFERENCES users(id),

    role                VARCHAR(20) NOT NULL,       -- 'user' | 'assistant' | 'system'
    content             TEXT NOT NULL,
    token_count         INTEGER DEFAULT 0,

    -- RAG metadata
    retrieved_chunks    JSONB,
    confidence_score    FLOAT,
    was_cached          BOOLEAN DEFAULT FALSE,

    -- Status
    is_in_context       BOOLEAN DEFAULT TRUE,
    is_summarized       BOOLEAN DEFAULT FALSE,

    created_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_msg_conv_created ON messages(conversation_id, created_at DESC);
CREATE INDEX idx_msg_context ON messages(conversation_id, is_in_context, created_at DESC);


-- ═══════════════════════════════════════════════════════════════════
-- 10. DOCUMENTS (PDF uploads)
-- ═══════════════════════════════════════════════════════════════════

CREATE TABLE documents (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    admin_id            UUID NOT NULL REFERENCES admins(id),
    filename            VARCHAR(255) NOT NULL,
    original_filename   VARCHAR(255) NOT NULL,
    file_size           BIGINT NOT NULL,
    mime_type           VARCHAR(100) NOT NULL,
    s3_key              VARCHAR(500) NOT NULL,          -- MinIO object key
    s3_bucket           VARCHAR(100) NOT NULL,

    -- Processing
    status              VARCHAR(20) DEFAULT 'uploaded',
                        -- uploaded | processing | processed | failed
    total_chunks        INTEGER DEFAULT 0,
    total_pages         INTEGER DEFAULT 0,
    processing_error    TEXT,
    processed_at        TIMESTAMPTZ,

    -- Metadata
    subject             VARCHAR(100),
    tags                JSONB DEFAULT '[]'::jsonb,
    description         TEXT,

    is_active           BOOLEAN DEFAULT TRUE,
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_documents_status ON documents(status);
CREATE INDEX idx_documents_subject ON documents(subject);


-- ═══════════════════════════════════════════════════════════════════
-- 11. DOCUMENT CHUNKS (RAG embeddings — 768d for nomic-embed-text)
-- ═══════════════════════════════════════════════════════════════════

CREATE TABLE document_chunks (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id         UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,

    chunk_index         INTEGER NOT NULL,
    content             TEXT NOT NULL,
    token_count         INTEGER DEFAULT 0,

    -- Embedding (1024 dimensions — mistral-embed)
    embedding           vector(1024),

    -- Metadata
    page_number         INTEGER,
    section_title       VARCHAR(255),
    metadata            JSONB DEFAULT '{}'::jsonb,

    created_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_chunks_document ON document_chunks(document_id);
-- HNSW index for fast similarity search
CREATE INDEX idx_chunks_embedding ON document_chunks
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);


-- ═══════════════════════════════════════════════════════════════════
-- 12. AI QUERIES (Audit trail)
-- ═══════════════════════════════════════════════════════════════════

CREATE TABLE ai_queries (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    conversation_id     UUID REFERENCES conversations(id),
    message_id          UUID REFERENCES messages(id),

    query_text          TEXT NOT NULL,
    response_text       TEXT,

    -- RAG details
    chunks_retrieved    INTEGER DEFAULT 0,
    retrieval_score     FLOAT,

    -- Token usage
    tokens_input        INTEGER DEFAULT 0,
    tokens_output       INTEGER DEFAULT 0,
    total_tokens        INTEGER DEFAULT 0,

    -- Performance
    response_time_ms    INTEGER,
    model_used          VARCHAR(50),
    was_cached          BOOLEAN DEFAULT FALSE,

    created_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_queries_user ON ai_queries(user_id);
CREATE INDEX idx_queries_conv ON ai_queries(conversation_id);
CREATE INDEX idx_queries_created ON ai_queries(created_at DESC);


-- ═══════════════════════════════════════════════════════════════════
-- 13. AUDIT LOGS
-- ═══════════════════════════════════════════════════════════════════

CREATE TABLE audit_logs (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    admin_id            UUID REFERENCES admins(id),
    action              VARCHAR(100) NOT NULL,
    resource_type       VARCHAR(50),            -- user, plan, document, etc.
    resource_id         UUID,
    details             JSONB,
    ip_address          INET,
    user_agent          TEXT,
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_audit_admin ON audit_logs(admin_id);
CREATE INDEX idx_audit_action ON audit_logs(action);
CREATE INDEX idx_audit_created ON audit_logs(created_at DESC);
CREATE INDEX idx_audit_resource ON audit_logs(resource_type, resource_id);


-- ═══════════════════════════════════════════════════════════════════
-- 14. ANALYTICS
-- ═══════════════════════════════════════════════════════════════════

CREATE TABLE analytics (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    metric_name         VARCHAR(100) NOT NULL,
    metric_value        FLOAT NOT NULL,
    dimensions          JSONB DEFAULT '{}'::jsonb,
    period_type         VARCHAR(10) NOT NULL,   -- 'daily' | 'weekly' | 'monthly'
    period_date         DATE NOT NULL,
    created_at          TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE(metric_name, period_type, period_date, dimensions)
);

CREATE INDEX idx_analytics_metric ON analytics(metric_name, period_date);


-- ═══════════════════════════════════════════════════════════════════
-- SEED DATA: Default Plans
-- ═══════════════════════════════════════════════════════════════════

INSERT INTO plans (
    name, display_name, description, price_inr, validity_days,
    messages_per_day, messages_per_month,
    max_conversations, max_active_conversations, conversation_timeout_min,
    max_context_messages, max_context_tokens, max_response_tokens,
    memory_retention_days, summary_frequency, long_term_memory_enabled,
    features
) VALUES
(
    'free', 'Free Plan', 'Get started with Vidhya Bot — basic access to AI-powered learning.',
    0, 36500,  -- ~100 years (never expires)
    5, 50,
    3, 1, 30,
    5, 2000, 512,
    7, 10, FALSE,
    '{"rag_enabled": true, "streaming_enabled": true, "history_export": false, "priority_queue": false, "subject_filter": false, "mcq_mode": false}'::jsonb
),
(
    'basic', 'Basic Plan', 'More messages and conversations for regular learners.',
    99, 30,
    30, 500,
    10, 2, 60,
    10, 4000, 1024,
    30, 10, FALSE,
    '{"rag_enabled": true, "streaming_enabled": true, "history_export": false, "priority_queue": false, "subject_filter": true, "mcq_mode": false}'::jsonb
),
(
    'premium', 'Premium Plan', 'Power user access with extended memory and context.',
    299, 30,
    100, 2000,
    25, 5, 120,
    20, 8000, 2048,
    90, 15, TRUE,
    '{"rag_enabled": true, "streaming_enabled": true, "history_export": true, "priority_queue": true, "subject_filter": true, "mcq_mode": true}'::jsonb
),
(
    'pro', 'Pro Plan', 'Unlimited access — the ultimate Vidhya Bot experience.',
    599, 30,
    -1, -1,   -- unlimited
    50, 10, 240,
    50, 16000, 4096,
    365, 20, TRUE,
    '{"rag_enabled": true, "streaming_enabled": true, "history_export": true, "priority_queue": true, "subject_filter": true, "mcq_mode": true}'::jsonb
);


-- ═══════════════════════════════════════════════════════════════════
-- SEED DATA: Default Superadmin
-- Password will be set via the create_admin.py script (Argon2id)
-- This is a PLACEHOLDER — the actual hash is set at runtime
-- ═══════════════════════════════════════════════════════════════════

-- Note: The admin account is created by the backend on first startup
-- using the ADMIN_DEFAULT_USERNAME and ADMIN_DEFAULT_PASSWORD env vars.
-- This ensures the password is properly hashed with Argon2id.


-- ═══════════════════════════════════════════════════════════════════
-- HELPER FUNCTION: Auto-update updated_at timestamp
-- ═══════════════════════════════════════════════════════════════════

CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply trigger to all tables with updated_at
CREATE TRIGGER trg_users_updated_at BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER trg_admins_updated_at BEFORE UPDATE ON admins
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER trg_plans_updated_at BEFORE UPDATE ON plans
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER trg_payments_updated_at BEFORE UPDATE ON payments
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER trg_subs_updated_at BEFORE UPDATE ON user_subscriptions
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER trg_usage_updated_at BEFORE UPDATE ON usage_tracking
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER trg_documents_updated_at BEFORE UPDATE ON documents
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();


-- ═══════════════════════════════════════════════════════════════════
-- VERIFICATION
-- ═══════════════════════════════════════════════════════════════════

DO $$
BEGIN
    RAISE NOTICE '══════════════════════════════════════════════════════';
    RAISE NOTICE '  VIDHYA BOT v3 — Database initialized successfully!';
    RAISE NOTICE '  Tables: 14 | Extensions: uuid-ossp, vector, pg_trgm';
    RAISE NOTICE '  Plans seeded: free, basic, premium, pro';
    RAISE NOTICE '══════════════════════════════════════════════════════';
END $$;
