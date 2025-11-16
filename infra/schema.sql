-- PostgreSQL schema for logistics documents with structured columns

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

-- Indexes for faster lookups
CREATE INDEX IF NOT EXISTS idx_document_hash ON logistics_documents(document_hash);
CREATE INDEX IF NOT EXISTS idx_filename ON logistics_documents(filename);
CREATE INDEX IF NOT EXISTS idx_tracking_number ON logistics_documents(tracking_number);
CREATE INDEX IF NOT EXISTS idx_shipment_date ON logistics_documents(shipment_date);
CREATE INDEX IF NOT EXISTS idx_carrier ON logistics_documents(carrier);
