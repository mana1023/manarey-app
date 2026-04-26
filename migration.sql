-- Create pending_increments table for PostgreSQL
-- This table batches stock increments to reduce DB load
CREATE TABLE IF NOT EXISTS pending_increments (
    producto_id INTEGER PRIMARY KEY,
    delta INTEGER NOT NULL DEFAULT 0,
    usuario TEXT,
    local TEXT,
    motivo TEXT,
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Create index for fast lookups by updated_at
CREATE INDEX IF NOT EXISTS idx_pending_increments_updated_at ON pending_increments(updated_at);
