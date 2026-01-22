-- Migration: add llm_model column to run_metadata

ALTER TABLE run_metadata
ADD COLUMN IF NOT EXISTS llm_model TEXT;

COMMENT ON COLUMN run_metadata.llm_model IS 'Selected LLM model for the run (optional)';
