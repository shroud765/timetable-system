-- M05/M15: run after a timetable has been generated. Read-only analysis.
-- Substitute an actual version, cohort and slot range for your test.
SET @v = (SELECT published FROM terms WHERE id=1);
SET @cohort = (SELECT id FROM resources WHERE kind='cohort' LIMIT 1);
EXPLAIN ANALYZE
SELECT id, requirement, teacher, cohort, room, slot, duration
FROM lessons
WHERE version=@v AND cohort=@cohort AND slot BETWEEN 0 AND 29
ORDER BY slot;
-- On tiny tables, a scan can be cheaper than an index. Do not force an index.
SELECT TABLE_NAME, INDEX_NAME, COLUMN_NAME, SEQ_IN_INDEX
FROM information_schema.STATISTICS
WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='lessons';
