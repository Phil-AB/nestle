"""add_universal_validation_and_storage_tables

Revision ID: 662967e5f41a
Revises: 7cccaf286a82
Create Date: 2025-11-23 19:18:40.935422

Adds tables for universal validation and storage system:
1. documents - Generic JSONB-based document storage
2. validation_results - Validation results and history
3. document_snapshots - Full document snapshots for audit trail
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID


# revision identifiers, used by Alembic.
revision = '662967e5f41a'
down_revision = '7cccaf286a82'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Generic documents table (JSONB-based flexible storage)
    op.create_table(
        'documents',
        sa.Column('id', UUID, primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('document_type', sa.String(100), nullable=False, index=True),
        sa.Column('data', JSONB, nullable=False),
        sa.Column('metadata', JSONB),
        sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime, nullable=False, server_default=sa.text('NOW()')),
    )
    
    # Indexes for fast JSONB queries
    op.create_index(
        'idx_documents_created_at',
        'documents',
        ['created_at'],
    )
    op.create_index(
        'idx_documents_data_gin',
        'documents',
        ['data'],
        postgresql_using='gin'
    )
    
    # 2. Validation results table
    op.create_table(
        'validation_results',
        sa.Column('id', UUID, primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('document_id', UUID, nullable=True),  # May reference documents or external docs
        sa.Column('document_type', sa.String(100), nullable=False),
        sa.Column('passed', sa.Boolean, nullable=False),
        sa.Column('score', sa.Numeric(5, 4)),
        sa.Column('total_checks', sa.Integer),
        sa.Column('passed_checks', sa.Integer),
        sa.Column('failed_checks', sa.Integer),
        sa.Column('warning_checks', sa.Integer),
        sa.Column('error_checks', sa.Integer),
        sa.Column('requires_review', sa.Boolean, default=False),
        sa.Column('results', JSONB),  # Array of ValidationResult objects
        sa.Column('summary', JSONB),  # ValidationSummary object
        sa.Column('metadata', JSONB),
        sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.text('NOW()')),
    )
    
    # Indexes for validation results
    op.create_index(
        'idx_validation_results_document_id',
        'validation_results',
        ['document_id'],
    )
    op.create_index(
        'idx_validation_results_created_at',
        'validation_results',
        ['created_at'],
    )
    op.create_index(
        'idx_validation_results_passed',
        'validation_results',
        ['passed'],
    )
    
    # 3. Document snapshots table (for audit trail and versioning)
    op.create_table(
        'document_snapshots',
        sa.Column('id', UUID, primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('document_id', UUID, nullable=False),
        sa.Column('document_type', sa.String(100), nullable=False),
        sa.Column('snapshot_type', sa.String(50)),  # created, updated, validated
        sa.Column('data', JSONB, nullable=False),  # Full document snapshot
        sa.Column('metadata', JSONB),
        sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.text('NOW()')),
    )
    
    # Indexes for snapshots
    op.create_index(
        'idx_document_snapshots_document_id',
        'document_snapshots',
        ['document_id'],
    )
    op.create_index(
        'idx_document_snapshots_created_at',
        'document_snapshots',
        ['created_at'],
    )


def downgrade() -> None:
    # Drop tables in reverse order
    op.drop_table('document_snapshots')
    op.drop_table('validation_results')
    op.drop_table('documents')
