-- Run order matters: categories first (FK target)

CREATE TABLE IF NOT EXISTS categories (
    id          SERIAL PRIMARY KEY,
    name        VARCHAR NOT NULL UNIQUE,
    group_name  VARCHAR,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS user_rules (
    id          SERIAL PRIMARY KEY,
    rule_type   VARCHAR NOT NULL,
    match_value VARCHAR NOT NULL,
    source      VARCHAR,
    category_id INTEGER NOT NULL REFERENCES categories(id),
    priority    INTEGER NOT NULL DEFAULT 100,
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    updated_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS system_rules (
    id          SERIAL PRIMARY KEY,
    rule_type   VARCHAR NOT NULL,
    keyword     VARCHAR,
    source      VARCHAR,
    type_code   VARCHAR,
    category_id INTEGER REFERENCES categories(id),
    priority    INTEGER NOT NULL DEFAULT 50,
    meta        JSONB
);

CREATE TABLE IF NOT EXISTS llm_cache (
    merchant_key  VARCHAR PRIMARY KEY,
    category_id   INTEGER NOT NULL REFERENCES categories(id),
    confidence    FLOAT NOT NULL,
    model_version VARCHAR NOT NULL,
    created_at    TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS pending_review (
    id              VARCHAR PRIMARY KEY,
    source          VARCHAR NOT NULL,
    description     VARCHAR NOT NULL,
    amount          DECIMAL(10,2) NOT NULL,
    direction       VARCHAR NOT NULL,
    llm_suggestion  INTEGER REFERENCES categories(id),
    llm_confidence  FLOAT,
    llm_reasoning   VARCHAR,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);
