-- Migration: add llm_model column to dynamic_skills

ALTER TABLE dynamic_skills
ADD COLUMN IF NOT EXISTS llm_model TEXT;

COMMENT ON COLUMN dynamic_skills.llm_model IS 'LLM model override for this skill (optional)';
