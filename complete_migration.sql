-- Complete migration script for pending_increments table
-- Run this to fix the "relation does not exist" error

-- Drop table if it exists (to ensure clean slate)
DROP TABLE IF EXISTS pending_increments;

-- Create table with correct schema matching the application code
CREATE TABLE pending_increments (
    producto_id INTEGER PRIMARY KEY,
    delta INTEGER NOT NULL DEFAULT 0,
    usuario TEXT,
    local TEXT,
    motivo TEXT,
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Create index for performance
CREATE INDEX IF NOT EXISTS idx_pending_increments_updated_at ON pending_increments(updated_at);

-- Verify the table was created
SELECT table_name, column_name, data_type 
FROM information_schema.columns 
WHERE table_name = 'pending_increments'
ORDER BY ordinal_position;
