-- Add action_functions column to dynamic_skills table
-- This stores Python functions used by data_pipeline transform steps

ALTER TABLE dynamic_skills 
ADD COLUMN IF NOT EXISTS action_functions TEXT;

COMMENT ON COLUMN dynamic_skills.action_functions IS 
'Python functions for data_pipeline transform steps';
