-- Single source of truth for the schema. It runs only on an empty volume,
-- so recreate the volume when changing the schema.

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "vector";       -- pgvector for RAG embeddings
CREATE EXTENSION IF NOT EXISTS "pg_trgm";      -- trigram for fuzzy text search


-- 1. USERS

CREATE TABLE users (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    telegram_id         BIGINT UNIQUE,                  -- nullable: web/admin accounts have none
    telegram_username   VARCHAR(100),
    username            VARCHAR(30) UNIQUE,
    email               VARCHAR(255) UNIQUE,
    mobile              VARCHAR(20) UNIQUE,
    password_hash       TEXT,                           -- Argon2id
    auth_provider       VARCHAR(20) DEFAULT 'telegram', -- telegram | web | admin
    email_verified_at   TIMESTAMPTZ,
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


-- 2. ADMINS

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


-- 2a. AI PROVIDERS + MODELS

CREATE TABLE ai_providers (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name              VARCHAR(80) NOT NULL UNIQUE,
    adapter           VARCHAR(30) NOT NULL DEFAULT 'openai_compatible',
    base_url          TEXT NOT NULL,
    chat_url          TEXT,
    embeddings_url    TEXT,
    models_url        TEXT,
    auth_type         VARCHAR(20) NOT NULL DEFAULT 'bearer',
    auth_key_name     VARCHAR(80),
    auth_username     VARCHAR(120),
    api_key_encrypted TEXT,
    is_active         BOOLEAN NOT NULL DEFAULT TRUE,
    created_by        UUID REFERENCES admins(id) ON DELETE SET NULL,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE ai_chat_models (
    id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    provider_id          UUID NOT NULL REFERENCES ai_providers(id) ON DELETE CASCADE,
    name                 VARCHAR(160) NOT NULL,
    display_name         VARCHAR(160) NOT NULL,
    context_window       INTEGER NOT NULL DEFAULT 32000,
    max_output_tokens    INTEGER NOT NULL DEFAULT 1024,
    system_prompt        TEXT NOT NULL DEFAULT '',
    is_active            BOOLEAN NOT NULL DEFAULT TRUE,
    is_default           BOOLEAN NOT NULL DEFAULT FALSE,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_ai_chat_model UNIQUE (provider_id, name)
);

CREATE INDEX ix_ai_chat_models_active ON ai_chat_models(is_active);
CREATE UNIQUE INDEX uq_ai_chat_default ON ai_chat_models (is_default)
    WHERE is_default = TRUE;

CREATE TABLE ai_embedding_models (
    id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    provider_id          UUID NOT NULL REFERENCES ai_providers(id) ON DELETE CASCADE,
    name                 VARCHAR(160) NOT NULL,
    display_name         VARCHAR(160) NOT NULL,
    embedding_dimensions INTEGER NOT NULL,
    is_active            BOOLEAN NOT NULL DEFAULT FALSE,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_ai_embedding_model UNIQUE (provider_id, name)
);

-- Only one embedding model may be active globally.
CREATE UNIQUE INDEX uq_ai_embedding_active ON ai_embedding_models (is_active)
    WHERE is_active = TRUE;


-- 2b. EMAIL OTP + USER API KEYS

CREATE TABLE email_otps (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    purpose         VARCHAR(30) NOT NULL,        -- verify_email | login | reset
    code_hash       VARCHAR(128) NOT NULL,
    attempts        INTEGER NOT NULL DEFAULT 0,
    expires_at      TIMESTAMPTZ NOT NULL,
    consumed_at     TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_email_otps_user ON email_otps(user_id, purpose);
CREATE INDEX idx_email_otps_created ON email_otps(created_at);

CREATE TABLE user_api_keys (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    label           VARCHAR(50) NOT NULL DEFAULT 'default',
    key_prefix      VARCHAR(16) NOT NULL,
    key_hash        VARCHAR(64) NOT NULL UNIQUE,
    is_enabled      BOOLEAN NOT NULL DEFAULT FALSE,
    created_by      UUID REFERENCES admins(id) ON DELETE SET NULL,
    last_used_at    TIMESTAMPTZ,
    revoked_at      TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_user_api_keys_user ON user_api_keys(user_id);


-- 3. SESSIONS

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


-- 4. PLANS — Full Control Layer

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
    max_sessions                INTEGER NOT NULL DEFAULT 3,

    -- Context / Token Controls
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


-- 5. PAYMENTS (multi-provider)

CREATE TABLE payment_providers (
    id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    driver                VARCHAR(40) NOT NULL,
    mode                  VARCHAR(20) NOT NULL
                          CHECK (mode IN ('demo', 'sandbox', 'production')),
    display_name          VARCHAR(120) NOT NULL,
    credentials_encrypted TEXT,
    config                JSONB NOT NULL DEFAULT '{}'::jsonb,
    is_active             BOOLEAN NOT NULL DEFAULT FALSE,
    last_tested_at        TIMESTAMPTZ,
    last_test_status      VARCHAR(20),
    last_test_error       TEXT,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_payment_provider_driver_mode UNIQUE (driver, mode)
);

-- Exactly one active provider per mode.
CREATE UNIQUE INDEX uq_payment_provider_active ON payment_providers (mode)
    WHERE is_active;

CREATE TABLE payment_orders (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    plan_id             UUID REFERENCES plans(id) ON DELETE SET NULL,
    provider_id         UUID REFERENCES payment_providers(id) ON DELETE SET NULL,
    provider_driver     VARCHAR(40) NOT NULL DEFAULT '',
    mode                VARCHAR(20) NOT NULL DEFAULT 'sandbox',
    is_test             BOOLEAN NOT NULL DEFAULT TRUE,
    order_ref           VARCHAR(64) NOT NULL UNIQUE,
    idempotency_key     VARCHAR(128),
    provider_order_id   VARCHAR(191),
    provider_payment_id VARCHAR(191),
    plan_name           VARCHAR(100),
    plan_snapshot       JSONB NOT NULL DEFAULT '{}'::jsonb,
    amount_paise        BIGINT NOT NULL,
    currency            VARCHAR(3) NOT NULL DEFAULT 'INR',
    status              VARCHAR(20) NOT NULL DEFAULT 'created',
    payment_method      VARCHAR(50),
    payment_url         TEXT,
    provider_payload    JSONB NOT NULL DEFAULT '{}'::jsonb,
    failure_reason      TEXT,
    expires_at          TIMESTAMPTZ,
    paid_at             TIMESTAMPTZ,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_payment_order_idem UNIQUE (user_id, idempotency_key)
);

CREATE INDEX ix_payment_orders_user ON payment_orders(user_id);
CREATE INDEX ix_payment_orders_status ON payment_orders(status);
CREATE INDEX ix_payment_orders_provider_order ON payment_orders(provider_order_id);

CREATE TABLE payment_events (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    provider_id     UUID REFERENCES payment_providers(id) ON DELETE SET NULL,
    order_id        UUID REFERENCES payment_orders(id) ON DELETE SET NULL,
    driver          VARCHAR(40) NOT NULL,
    mode            VARCHAR(20) NOT NULL,
    event_id        VARCHAR(191) NOT NULL,
    event_type      VARCHAR(80),
    signature_valid BOOLEAN NOT NULL DEFAULT FALSE,
    payload_hash    VARCHAR(64) NOT NULL,
    status          VARCHAR(20) NOT NULL DEFAULT 'received',
    error           TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_payment_event UNIQUE (provider_id, event_id)
);

CREATE INDEX ix_payment_events_provider ON payment_events(provider_id);
CREATE INDEX ix_payment_events_order ON payment_events(order_id);


-- 6. USER SUBSCRIPTIONS

CREATE TABLE user_subscriptions (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id                 UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    plan_id                 UUID NOT NULL REFERENCES plans(id),
    payment_id              UUID REFERENCES payment_orders(id),

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


-- 7. USAGE TRACKING

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


-- 8. CONVERSATIONS

CREATE TABLE conversations (
    id                          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id                     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    subscription_id             UUID REFERENCES user_subscriptions(id),

    title                       VARCHAR(255),

    -- Plan limits snapshot (captured when the session starts)
    max_context_tokens          INTEGER NOT NULL,
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

    created_at                  TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_conv_user_activity ON conversations(user_id, last_activity_at DESC);


-- 9. MESSAGES

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


-- 10. DOCUMENTS (PDF uploads)

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
    processed_chunks    INTEGER DEFAULT 0,
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


-- 11. DOCUMENT CHUNKS (RAG embeddings — 768d for nomic-embed-text)

CREATE TABLE document_chunks (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id         UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,

    chunk_index         INTEGER NOT NULL,
    content             TEXT NOT NULL,
    token_count         INTEGER DEFAULT 0,

    -- Embedding (1024 dimensions) + which model produced it
    embedding           vector(1024),
    embedding_model_id  UUID REFERENCES ai_embedding_models(id) ON DELETE SET NULL,

    -- Metadata
    page_number         INTEGER,
    section_title       VARCHAR(255),
    metadata            JSONB DEFAULT '{}'::jsonb,

    created_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_chunks_document ON document_chunks(document_id);
CREATE INDEX idx_chunks_embedding_model ON document_chunks(embedding_model_id);
-- HNSW index for fast similarity search
CREATE INDEX idx_chunks_embedding ON document_chunks
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);


-- 12. AI QUERIES (Audit trail)

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


-- 13. AUDIT LOGS

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


-- 14. ANALYTICS

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


-- SEED DATA: Default Plans

INSERT INTO plans (
    name, display_name, description, price_inr, validity_days,
    messages_per_day, messages_per_month,
    max_sessions,
    max_context_tokens, max_response_tokens,
    memory_retention_days, summary_frequency, long_term_memory_enabled,
    features
) VALUES
(
    'free', 'Free Plan', 'Get started with Vidhya Bot — basic access to AI-powered learning.',
    0, 36500,  -- ~100 years (never expires)
    5, 50,
    5,
    2000, 512,
    7, 10, FALSE,
    '{"rag_enabled": true, "streaming_enabled": true, "history_export": false, "priority_queue": false, "subject_filter": false, "mcq_mode": false}'::jsonb
),
(
    'basic', 'Basic Plan', 'More messages and conversations for regular learners.',
    99, 30,
    30, 500,
    10,
    4000, 1024,
    30, 10, FALSE,
    '{"rag_enabled": true, "streaming_enabled": true, "history_export": false, "priority_queue": false, "subject_filter": true, "mcq_mode": false}'::jsonb
),
(
    'premium', 'Premium Plan', 'Power user access with extended memory and context.',
    299, 30,
    100, 2000,
    25,
    8000, 2048,
    90, 15, TRUE,
    '{"rag_enabled": true, "streaming_enabled": true, "history_export": true, "priority_queue": true, "subject_filter": true, "mcq_mode": true}'::jsonb
),
(
    'pro', 'Pro Plan', 'Unlimited access — the ultimate Vidhya Bot experience.',
    599, 30,
    -1, -1,   -- unlimited
    50,
    16000, 4096,
    365, 20, TRUE,
    '{"rag_enabled": true, "streaming_enabled": true, "history_export": true, "priority_queue": true, "subject_filter": true, "mcq_mode": true}'::jsonb
);


-- SEED DATA: Default Superadmin
-- Password will be set via the create_admin.py script (Argon2id)
-- This is a PLACEHOLDER — the actual hash is set at runtime

-- Note: The admin account is created by the backend on first startup
-- using the ADMIN_DEFAULT_USERNAME and ADMIN_DEFAULT_PASSWORD env vars.
-- This ensures the password is properly hashed with Argon2id.


-- PLATFORM SETTINGS (paid / free mode)

CREATE TABLE IF NOT EXISTS platform_settings (
    id              INTEGER PRIMARY KEY DEFAULT 1,
    platform_mode   VARCHAR(10) NOT NULL DEFAULT 'paid'
                    CHECK (platform_mode IN ('paid', 'free')),
    registration_enabled BOOLEAN NOT NULL DEFAULT FALSE,
    email_otp_login      BOOLEAN NOT NULL DEFAULT FALSE,
    bot_settings         JSONB NOT NULL DEFAULT '{}'::jsonb,
    payments_environment VARCHAR(20) NOT NULL DEFAULT 'demo'
                    CHECK (payments_environment IN ('demo', 'sandbox', 'production')),
    default_chat_model_id      UUID REFERENCES ai_chat_models(id) ON DELETE SET NULL,
    reindex_status             VARCHAR(20) NOT NULL DEFAULT 'idle',
    reindex_target_model_id    UUID REFERENCES ai_embedding_models(id) ON DELETE SET NULL,
    reindex_total              INTEGER NOT NULL DEFAULT 0,
    reindex_done               INTEGER NOT NULL DEFAULT 0,
    reindex_failed             INTEGER NOT NULL DEFAULT 0,
    reindex_started_at         TIMESTAMPTZ,
    reindex_completed_at       TIMESTAMPTZ,
    reindex_error              TEXT,
    embedding_dimensions       INTEGER NOT NULL DEFAULT 1024,
    mode_changed_at TIMESTAMPTZ,
    mode_changed_by UUID REFERENCES admins(id) ON DELETE SET NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

INSERT INTO platform_settings (id, platform_mode) VALUES (1, 'paid')
ON CONFLICT (id) DO NOTHING;


-- HELPER FUNCTION: Auto-update updated_at timestamp

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

CREATE TRIGGER trg_platform_settings_updated_at BEFORE UPDATE ON platform_settings
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER trg_user_api_keys_updated_at BEFORE UPDATE ON user_api_keys
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER trg_ai_providers_updated_at BEFORE UPDATE ON ai_providers
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER trg_ai_chat_models_updated_at BEFORE UPDATE ON ai_chat_models
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER trg_ai_embedding_models_updated_at BEFORE UPDATE ON ai_embedding_models
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER trg_payment_providers_updated_at BEFORE UPDATE ON payment_providers
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER trg_payment_orders_updated_at BEFORE UPDATE ON payment_orders
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER trg_subs_updated_at BEFORE UPDATE ON user_subscriptions
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER trg_usage_updated_at BEFORE UPDATE ON usage_tracking
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER trg_documents_updated_at BEFORE UPDATE ON documents
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();


DO $$
BEGIN
    RAISE NOTICE 'Vidhya database initialized: 22 tables, uuid-ossp, vector and pg_trgm ready';
END $$;
