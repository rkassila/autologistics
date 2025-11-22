-- PostgreSQL schema for model log table
-- Tracks whether model extractions were successful (no manual corrections) or required corrections
-- Created in the same database as logistics_db table

CREATE TABLE IF NOT EXISTS model_log (
    id SERIAL PRIMARY KEY,
    success BOOLEAN NOT NULL,  -- true if no corrections needed, false if corrections were made
    document_id INTEGER,  -- References logistics_db.id (foreign key constraint can be added later if needed)
    document_hash VARCHAR(64) NOT NULL,
    document_link VARCHAR(500),  -- storage_url from logistics_db table
    extraction_result JSONB,  -- Full extraction response/prompt output
    original_values JSONB,  -- Original extracted field values
    corrected_values JSONB,  -- Final corrected values (what was saved)
    corrections_made JSONB,  -- Map of field changes: {"field_name": {"original": "X", "corrected": "Y"}}
    failure_reason TEXT,  -- If success=false, reason why corrections were needed
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for faster queries
CREATE INDEX IF NOT EXISTS idx_model_log_document_id ON model_log(document_id);
CREATE INDEX IF NOT EXISTS idx_model_log_document_hash ON model_log(document_hash);
CREATE INDEX IF NOT EXISTS idx_model_log_success ON model_log(success);
CREATE INDEX IF NOT EXISTS idx_model_log_created_at ON model_log(created_at);
