-- Migration: Add generic_documents table for handling any document type
-- Date: 2025-11-25
-- Description: Creates a flexible generic_documents table to store any document type
--              that doesn't have a specific configuration (invoice, boe, etc.)

CREATE TABLE IF NOT EXISTS generic_documents (
    id SERIAL PRIMARY KEY,
    document_id VARCHAR(100) NOT NULL UNIQUE,
    document_type VARCHAR(100) NOT NULL,
    document_number VARCHAR(100),

    -- Flexible JSON storage for all extracted fields
    extracted_data JSONB,
    raw_data JSONB,

    -- Metadata
    status VARCHAR(50) DEFAULT 'approved',
    confidence NUMERIC(5, 2),
    extraction_status VARCHAR(50) DEFAULT 'complete',

    -- Timestamps
    parsed_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,

    -- Indexes
    CONSTRAINT generic_documents_document_id_key UNIQUE (document_id)
);

-- Create indexes for better query performance
CREATE INDEX IF NOT EXISTS idx_generic_documents_document_type ON generic_documents(document_type);
CREATE INDEX IF NOT EXISTS idx_generic_documents_document_number ON generic_documents(document_number);
CREATE INDEX IF NOT EXISTS idx_generic_documents_document_id ON generic_documents(document_id);

-- Add trigger to auto-update updated_at timestamp
CREATE OR REPLACE FUNCTION update_generic_documents_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_generic_documents_updated_at
    BEFORE UPDATE ON generic_documents
    FOR EACH ROW
    EXECUTE FUNCTION update_generic_documents_updated_at();

-- Success message
DO $$
BEGIN
    RAISE NOTICE 'generic_documents table created successfully!';
END $$;
