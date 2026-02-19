-- Generic application configuration table.
-- Stores admin-managed settings for feature toggles and future options.

CREATE TABLE IF NOT EXISTS app_config (
    config_key TEXT PRIMARY KEY,
    config_value JSONB NOT NULL,
    description TEXT,
    updated_by TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_app_config_updated_at ON app_config(updated_at DESC);

-- Default feature toggle: enabled by default
INSERT INTO app_config (config_key, config_value, description)
VALUES (
    'feature.agentic_view_enabled',
    '{"enabled": true}'::jsonb,
    'Enable/disable Agentic View tab and rendering'
)
ON CONFLICT (config_key) DO NOTHING;
