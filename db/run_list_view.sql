-- View for runs list with computed status and metadata
-- This view enriches checkpoint data with derived fields for the admin UI

CREATE OR REPLACE VIEW run_list_view AS
SELECT 
    c.thread_id,
    c.checkpoint_id,
    c.checkpoint_ns,
    -- Extract active_skill from checkpoint JSONB
    COALESCE(
        c.checkpoint->'channel_values'->>'active_skill',
        c.checkpoint->>'active_skill'
    ) as active_skill,
    -- Extract history array length
    COALESCE(
        jsonb_array_length(c.checkpoint->'channel_values'->'history'),
        jsonb_array_length(c.checkpoint->'history'),
        0
    ) as history_count,
    -- Compute status based on active_skill and history
    CASE
        -- Explicitly marked as END
        WHEN COALESCE(
            c.checkpoint->'channel_values'->>'active_skill',
            c.checkpoint->>'active_skill'
        ) = 'END' THEN 'completed'
        
        -- Check if history contains completion markers
        WHEN EXISTS (
            SELECT 1 FROM jsonb_array_elements_text(
                COALESCE(
                    c.checkpoint->'channel_values'->'history',
                    c.checkpoint->'history',
                    '[]'::jsonb
                )
            ) AS history_item
            WHERE LOWER(history_item) LIKE '%reached end%'
               OR LOWER(history_item) LIKE '%execution completed%'
               OR LOWER(history_item) LIKE '%planner chose end%'
        ) THEN 'completed'
        
        -- Check if awaiting human review (paused state)
        WHEN EXISTS (
            SELECT 1 FROM jsonb_array_elements_text(
                COALESCE(
                    c.checkpoint->'channel_values'->'history',
                    c.checkpoint->'history',
                    '[]'::jsonb
                )
            ) AS history_item
            WHERE LOWER(history_item) LIKE '%awaiting human review%'
               OR LOWER(history_item) LIKE '%redirecting to human_review%'
        ) AND COALESCE(
            c.checkpoint->'channel_values'->>'active_skill',
            c.checkpoint->>'active_skill'
        ) IS NULL THEN 'paused'
        
        -- Active skill exists and is not END
        WHEN COALESCE(
            c.checkpoint->'channel_values'->>'active_skill',
            c.checkpoint->>'active_skill'
        ) IS NOT NULL 
        AND COALESCE(
            c.checkpoint->'channel_values'->>'active_skill',
            c.checkpoint->>'active_skill'
        ) != 'END' THEN 'running'
        
        -- Has history but no active skill (check if truly completed or just paused)
        WHEN COALESCE(
            jsonb_array_length(c.checkpoint->'channel_values'->'history'),
            jsonb_array_length(c.checkpoint->'history'),
            0
        ) > 0 
        AND COALESCE(
            c.checkpoint->'channel_values'->>'active_skill',
            c.checkpoint->>'active_skill'
        ) IS NULL THEN 'completed'
        
        -- Default to pending
        ELSE 'pending'
    END as status,
    -- Extract layman_sop for preview
    LEFT(
        COALESCE(
            c.checkpoint->'channel_values'->>'layman_sop',
            c.checkpoint->>'layman_sop',
            ''
        ),
        200
    ) as sop_preview,
    -- Timestamp from metadata
    COALESCE(
        (c.metadata->>'ts')::timestamp with time zone,
        (c.metadata->>'updated_at')::timestamp with time zone
    ) as updated_at,
    -- Full checkpoint and metadata for details
    c.checkpoint,
    c.metadata
FROM checkpoints c
WHERE c.checkpoint_ns = ''  -- Only root checkpoints
ORDER BY updated_at DESC NULLS LAST;

-- Note: We don't create additional indexes here as the checkpoint table
-- already has indexes from LangGraph. JSONB operators in computed columns
-- cannot be used in indexes without IMMUTABLE functions.

COMMENT ON VIEW run_list_view IS 'Enriched view of workflow runs with computed status and metadata for admin UI';

