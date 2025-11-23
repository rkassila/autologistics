-- PostgreSQL schema for logistics_db database
-- Contains two tables: logistics_documents and model_log

-- Table 1: Logistics Documents
CREATE TABLE IF NOT EXISTS logistics_documents (
    id SERIAL PRIMARY KEY,
    filename VARCHAR(255) NOT NULL,
    storage_url VARCHAR(500),  -- GCP Cloud Storage URL
    extracted_text TEXT,
    document_hash VARCHAR(64) UNIQUE NOT NULL,

    -- Structured extracted fields
    tracking_number VARCHAR(100),
    shipper_name VARCHAR(255),
    shipper_address TEXT,
    receiver_name VARCHAR(255),
    receiver_address TEXT,
    shipment_date DATE,
    delivery_date DATE,
    weight VARCHAR(50),
    dimensions VARCHAR(100),
    carrier VARCHAR(100),
    shipping_method VARCHAR(100),
    status VARCHAR(50),
    special_instructions TEXT,

    -- Additional structured data as JSONB for flexibility
    additional_data JSONB,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Table 2: Model Log
-- Tracks whether model extractions were successful (no manual corrections) or required corrections
CREATE TABLE IF NOT EXISTS model_log (
    id SERIAL PRIMARY KEY,
    success BOOLEAN NOT NULL,  -- true if no corrections needed, false if corrections were made
    document_id INTEGER,  -- References logistics_documents.id (foreign key constraint can be added later if needed)
    document_hash VARCHAR(64) NOT NULL,
    document_link VARCHAR(500),  -- storage_url from logistics_documents table
    extraction_result JSONB,  -- Full extraction response/prompt output
    original_values JSONB,  -- Original extracted field values
    corrected_values JSONB,  -- Final corrected values (what was saved)
    corrections_made JSONB,  -- Map of field changes: {"field_name": {"original": "X", "corrected": "Y"}}
    failure_reason TEXT,  -- If success=false, reason why corrections were needed
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for logistics_documents
CREATE INDEX IF NOT EXISTS idx_logistics_documents_tracking_number ON logistics_documents(tracking_number);
CREATE INDEX IF NOT EXISTS idx_logistics_documents_carrier ON logistics_documents(carrier);
CREATE INDEX IF NOT EXISTS idx_logistics_documents_shipment_date ON logistics_documents(shipment_date);
CREATE INDEX IF NOT EXISTS idx_logistics_documents_document_hash ON logistics_documents(document_hash);

-- Indexes for model_log
CREATE INDEX IF NOT EXISTS idx_model_log_document_id ON model_log(document_id);
CREATE INDEX IF NOT EXISTS idx_model_log_document_hash ON model_log(document_hash);
CREATE INDEX IF NOT EXISTS idx_model_log_success ON model_log(success);
CREATE INDEX IF NOT EXISTS idx_model_log_created_at ON model_log(created_at);
