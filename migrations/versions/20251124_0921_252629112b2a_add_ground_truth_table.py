"""add_ground_truth_table

Revision ID: 252629112b2a
Revises: 662967e5f41a
Create Date: 2025-11-24 09:21:29.095178

Adds ground_truth table for storing manually verified data.
Used for accuracy validation against human-verified correct values.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID


# revision identifiers, used by Alembic.
revision = '252629112b2a'
down_revision = '662967e5f41a'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create ground_truth table
    op.create_table(
        'ground_truth',
        sa.Column('id', UUID, primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('document_id', UUID, nullable=True),  # Reference to documents table
        sa.Column('document_type', sa.String(100), nullable=False),
        sa.Column('verified_data', JSONB, nullable=False),  # The correct values
        sa.Column('verified_by', sa.String(100)),
        sa.Column('verified_at', sa.DateTime, server_default=sa.text('NOW()')),
        sa.Column('verification_method', sa.String(50)),  # manual, automated, reference_system
        sa.Column('confidence_level', sa.String(20)),  # high, medium, low
        sa.Column('notes', sa.Text),
        sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime, nullable=False, server_default=sa.text('NOW()')),
    )
    
    # Indexes for fast lookups
    op.create_index(
        'idx_ground_truth_document_id',
        'ground_truth',
        ['document_id'],
    )
    op.create_index(
        'idx_ground_truth_document_type',
        'ground_truth',
        ['document_type'],
    )
    op.create_index(
        'idx_ground_truth_verified_data_gin',
        'ground_truth',
        ['verified_data'],
        postgresql_using='gin'
    )


def downgrade() -> None:
    op.drop_table('ground_truth')
