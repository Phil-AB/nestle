-- Create api_documents table for API document metadata storage
-- Replaces in-memory _documents_storage for production scalability

CREATE TABLE IF NOT EXISTS api_documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Document identification
    document_id VARCHAR(100) UNIQUE NOT NULL,
    document_type VARCHAR(100) NOT NULL,
    document_name VARCHAR(255),
    filename VARCHAR(255),

    -- File storage
    file_path TEXT NOT NULL,
    file_size INTEGER,
    is_multi_page BOOLEAN DEFAULT FALSE,
    total_pages INTEGER,

    -- Extraction configuration
    extraction_mode VARCHAR(50),
    extraction_status VARCHAR(50) NOT NULL,

    -- Relationships
    shipment_id VARCHAR(100),

    -- Extracted data (JSONB for efficient querying)
    fields JSONB DEFAULT '{}',
    items JSONB DEFAULT '[]',
    blocks JSONB DEFAULT '[]',
    doc_metadata JSONB DEFAULT '{}',
    raw_provider_response JSONB DEFAULT '{}',

    -- Counts
    items_count INTEGER DEFAULT 0,
    fields_count INTEGER DEFAULT 0,

    -- Quality metrics
    extraction_confidence REAL,

    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    parsed_at TIMESTAMP WITH TIME ZONE
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_api_documents_document_id ON api_documents(document_id);
CREATE INDEX IF NOT EXISTS idx_api_documents_document_type ON api_documents(document_type);
CREATE INDEX IF NOT EXISTS idx_api_documents_extraction_status ON api_documents(extraction_status);
CREATE INDEX IF NOT EXISTS idx_api_documents_shipment_id ON api_documents(shipment_id);
CREATE INDEX IF NOT EXISTS idx_api_documents_created_at ON api_documents(created_at DESC);

-- Trigger to auto-update updated_at
CREATE OR REPLACE FUNCTION update_api_documents_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_api_documents_updated_at
    BEFORE UPDATE ON api_documents
    FOR EACH ROW
    EXECUTE FUNCTION update_api_documents_updated_at();

COMMENT ON TABLE api_documents IS 'API document metadata storage - replaces in-memory dict for scalability';
