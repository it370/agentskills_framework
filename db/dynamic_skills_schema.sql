-- Schema for storing dynamic skills created via UI
-- Skills can exist in filesystem (skills/*.md) or database
-- Both sources are loaded at startup/reload

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Function to convert skill name to valid Python module name
CREATE OR REPLACE FUNCTION generate_module_name(skill_name TEXT)
RETURNS TEXT AS $$
BEGIN
    -- Convert to lowercase, replace special chars with underscores
    -- Remove consecutive underscores and trim
    RETURN TRIM(BOTH '_' FROM 
        REGEXP_REPLACE(
            REGEXP_REPLACE(
                LOWER(skill_name), 
                '[^a-z0-9_]', 
                '_', 
                'g'
            ),
            '_+',
            '_',
            'g'
        )
    );
END;
$$ LANGUAGE plpgsql IMMUTABLE;

CREATE TABLE IF NOT EXISTS dynamic_skills (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name TEXT UNIQUE NOT NULL,
    module_name TEXT UNIQUE NOT NULL,
    description TEXT NOT NULL,
    requires JSONB DEFAULT '[]'::jsonb,
    produces JSONB DEFAULT '[]'::jsonb,
    optional_produces JSONB DEFAULT '[]'::jsonb,
    executor TEXT NOT NULL DEFAULT 'llm',  -- 'llm', 'rest', 'action'
    hitl_enabled BOOLEAN DEFAULT FALSE,
    
    -- LLM executor fields
    prompt TEXT,
    system_prompt TEXT,
    
    -- REST executor fields
    rest_config JSONB,  -- {url, method, timeout, headers}
    
    -- ACTION executor fields
    action_config JSONB,  -- {type, query, credential_ref, etc}
    action_code TEXT,  -- Python code for python_function actions
    
    -- Metadata
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_by TEXT DEFAULT 'system',
    source TEXT DEFAULT 'database',  -- 'database' or 'filesystem'
    enabled BOOLEAN DEFAULT TRUE,
    
    CONSTRAINT valid_executor CHECK (executor IN ('llm', 'rest', 'action'))
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_dynamic_skills_name ON dynamic_skills(name);
CREATE INDEX IF NOT EXISTS idx_dynamic_skills_module_name ON dynamic_skills(module_name);
CREATE INDEX IF NOT EXISTS idx_dynamic_skills_enabled ON dynamic_skills(enabled);
CREATE INDEX IF NOT EXISTS idx_dynamic_skills_source ON dynamic_skills(source);

-- Auto-update updated_at timestamp
CREATE OR REPLACE FUNCTION update_dynamic_skills_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_dynamic_skills_timestamp
    BEFORE UPDATE ON dynamic_skills
    FOR EACH ROW
    EXECUTE FUNCTION update_dynamic_skills_timestamp();

-- Auto-generate module_name from name
CREATE OR REPLACE FUNCTION auto_generate_module_name()
RETURNS TRIGGER AS $$
BEGIN
    NEW.module_name = generate_module_name(NEW.name);
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_auto_generate_module_name
    BEFORE INSERT OR UPDATE OF name ON dynamic_skills
    FOR EACH ROW
    EXECUTE FUNCTION auto_generate_module_name();

-- Comments
COMMENT ON TABLE dynamic_skills IS 'Dynamic skills created via UI, loaded alongside filesystem skills at runtime';
COMMENT ON COLUMN dynamic_skills.id IS 'UUID primary key';
COMMENT ON COLUMN dynamic_skills.name IS 'Unique skill name (must not conflict with filesystem skills)';
COMMENT ON COLUMN dynamic_skills.module_name IS 'Auto-generated Python module name from skill name (lowercase, valid identifier)';
COMMENT ON COLUMN dynamic_skills.executor IS 'Execution method: llm (LLM-based), rest (API call), action (deterministic function)';
COMMENT ON COLUMN dynamic_skills.action_code IS 'Python function code for action executor (if type=python_function)';
COMMENT ON COLUMN dynamic_skills.source IS 'Where skill was defined: database (UI) or filesystem (.md files)';
COMMENT ON COLUMN dynamic_skills.enabled IS 'Whether skill is active (allows disabling without deletion)';
