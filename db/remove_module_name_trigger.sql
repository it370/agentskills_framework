-- Migration: Remove auto_generate_module_name trigger
-- Module naming is now handled purely in application code (skill_manager.py)
-- to avoid trigger conflicts and ensure predictable behavior.

-- Drop the trigger if it exists
DROP TRIGGER IF EXISTS trigger_auto_generate_module_name ON dynamic_skills;

-- Drop the trigger function (but keep generate_module_name function for Python to use)
DROP FUNCTION IF EXISTS auto_generate_module_name();

-- Comment update
COMMENT ON TABLE dynamic_skills IS 'Dynamic skills created via UI. Module names are computed in Python code, not triggers.';
