-- View for runs list with computed status and metadata
-- This view enriches checkpoint data with derived fields for the admin UI

-- Drop existing view first since we're changing the column structure
DROP VIEW IF EXISTS run_list_view CASCADE;

CREATE VIEW run_list_view AS
WITH thread_start_times AS (
    -- Get the earliest timestamp for each thread (when it was created)
    SELECT 
        thread_id,
        MIN(COALESCE(
            (checkpoint->>'ts')::timestamp with time zone,
            (metadata->>'ts')::timestamp with time zone
        )) as created_at
    FROM checkpoints
    WHERE checkpoint_ns = ''
    GROUP BY thread_id
),
latest_checkpoints AS (
    -- Get the LATEST checkpoint for each thread (for current status)
    SELECT DISTINCT ON (thread_id)
        thread_id,
        checkpoint_id,
        checkpoint_ns,
        checkpoint,
        metadata,
        COALESCE(
            (checkpoint->>'ts')::timestamp with time zone,
            (metadata->>'ts')::timestamp with time zone
        ) as updated_at
    FROM checkpoints
    WHERE checkpoint_ns = ''
    ORDER BY thread_id, COALESCE(
        (checkpoint->>'ts')::timestamp with time zone,
        (metadata->>'ts')::timestamp with time zone
    ) DESC NULLS LAST
)
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
        
        -- Check if at human_review interrupt (most reliable indicator)
        WHEN c.checkpoint->'channel_values'->'branch:to:human_review' IS NOT NULL 
        OR c.checkpoint->'branch:to:human_review' IS NOT NULL THEN 'paused'
        
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
        
        -- Check if awaiting human review (from history as fallback)
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
               OR LOWER(history_item) LIKE '%hitl enabled%'
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
    -- Timestamp from latest checkpoint (most recent activity)
    c.updated_at,
    -- Thread creation timestamp (from CTE join)
    ts.created_at,
    -- Full checkpoint and metadata for details
    c.checkpoint,
    c.metadata
FROM latest_checkpoints c
INNER JOIN thread_start_times ts ON c.thread_id = ts.thread_id
ORDER BY ts.created_at DESC NULLS LAST;

COMMENT ON VIEW run_list_view IS 'Enriched view of workflow runs with computed status and metadata for admin UI. Shows one row per thread (latest checkpoint), ordered by most recent activity first.';

