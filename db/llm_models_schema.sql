-- Schema for supported LLM models and API keys
-- This table stores the manual list of allowed models for selection

CREATE TABLE IF NOT EXISTS llm_models (
    id BIGSERIAL PRIMARY KEY,
    provider TEXT NOT NULL,
    model_name TEXT NOT NULL UNIQUE,
    api_key TEXT NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    is_default BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Ensure only one default model at a time
CREATE UNIQUE INDEX IF NOT EXISTS idx_llm_models_default
    ON llm_models (is_default)
    WHERE is_default = TRUE;

CREATE INDEX IF NOT EXISTS idx_llm_models_active ON llm_models(is_active);
CREATE INDEX IF NOT EXISTS idx_llm_models_provider ON llm_models(provider);

COMMENT ON TABLE llm_models IS 'Supported LLM models and API keys for manual selection';
COMMENT ON COLUMN llm_models.provider IS 'Provider name (openai, grok, gemini, etc.)';
COMMENT ON COLUMN llm_models.model_name IS 'Model identifier used by clients';
COMMENT ON COLUMN llm_models.api_key IS 'API key used to access the model';
COMMENT ON COLUMN llm_models.is_default IS 'Marks the default model used when no selection provided';
