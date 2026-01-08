-- =====================================================
-- CLEANUP SCRIPT - Remove all workflow runs and logs
-- =====================================================
-- 
-- WARNING: This will permanently delete ALL workflow data!
-- - All workflow runs (checkpoints)
-- - All execution history
-- - All logs
-- 
-- Use this to start fresh during development.
-- DO NOT run this in production without backups!
-- =====================================================

-- Show current counts before deletion
DO $$
DECLARE
    checkpoint_count INTEGER;
    log_count INTEGER;
    blob_count INTEGER;
    write_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO checkpoint_count FROM checkpoints;
    SELECT COUNT(*) INTO log_count FROM thread_logs;
    SELECT COUNT(*) INTO blob_count FROM checkpoint_blobs;
    SELECT COUNT(*) INTO write_count FROM checkpoint_writes;
    
    RAISE NOTICE '================================================';
    RAISE NOTICE 'Current database state:';
    RAISE NOTICE '================================================';
    RAISE NOTICE 'Checkpoints:        %', checkpoint_count;
    RAISE NOTICE 'Thread logs:        %', log_count;
    RAISE NOTICE 'Checkpoint blobs:   %', blob_count;
    RAISE NOTICE 'Checkpoint writes:  %', write_count;
    RAISE NOTICE '================================================';
    RAISE NOTICE 'All records will be DELETED!';
    RAISE NOTICE '================================================';
END $$;

-- Delete all thread logs
TRUNCATE TABLE thread_logs;

-- Delete all LangGraph checkpoint data
TRUNCATE TABLE checkpoint_writes CASCADE;
TRUNCATE TABLE checkpoint_blobs CASCADE;
TRUNCATE TABLE checkpoints CASCADE;

-- Reset sequences (optional - starts IDs from 1 again)
ALTER SEQUENCE IF EXISTS thread_logs_id_seq RESTART WITH 1;

-- Verify cleanup
DO $$
DECLARE
    checkpoint_count INTEGER;
    log_count INTEGER;
    blob_count INTEGER;
    write_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO checkpoint_count FROM checkpoints;
    SELECT COUNT(*) INTO log_count FROM thread_logs;
    SELECT COUNT(*) INTO blob_count FROM checkpoint_blobs;
    SELECT COUNT(*) INTO write_count FROM checkpoint_writes;
    
    RAISE NOTICE '================================================';
    RAISE NOTICE 'Cleanup complete! New state:';
    RAISE NOTICE '================================================';
    RAISE NOTICE 'Checkpoints:        %', checkpoint_count;
    RAISE NOTICE 'Thread logs:        %', log_count;
    RAISE NOTICE 'Checkpoint blobs:   %', blob_count;
    RAISE NOTICE 'Checkpoint writes:  %', write_count;
    RAISE NOTICE '================================================';
    RAISE NOTICE 'Database is now clean and ready for fresh runs!';
    RAISE NOTICE '================================================';
END $$;

