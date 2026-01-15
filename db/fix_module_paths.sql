-- Fix existing skills to use correct module_name in action_config
-- This script updates action_config.module to use the sanitized module_name
-- instead of the raw skill name

BEGIN;

-- Update python_function action skills to use correct module path
UPDATE dynamic_skills
SET action_config = jsonb_set(
    action_config,
    '{module}',
    to_jsonb('dynamic_skills.' || module_name)
)
WHERE executor = 'action'
  AND action_config->>'type' = 'python_function'
  AND action_config ? 'module';

-- Show updated skills
SELECT 
    name,
    module_name,
    action_config->>'module' as module_path,
    action_config->>'function' as function_name
FROM dynamic_skills
WHERE executor = 'action'
  AND action_config->>'type' = 'python_function';

COMMIT;

-- Verification
-- Check if any skills still have mismatched module paths
SELECT 
    name,
    module_name,
    action_config->>'module' as current_module,
    'dynamic_skills.' || module_name as expected_module,
    CASE 
        WHEN action_config->>'module' = 'dynamic_skills.' || module_name THEN '✓ Correct'
        ELSE '✗ Mismatch'
    END as status
FROM dynamic_skills
WHERE executor = 'action'
  AND action_config->>'type' = 'python_function';
