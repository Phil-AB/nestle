"""add_extraction_status_and_raw_data_columns

Revision ID: 7cccaf286a82
Revises: 697b41a5d33b
Create Date: 2025-11-12 10:54:54.157890

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '7cccaf286a82'
down_revision = '697b41a5d33b'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create extraction status enum
    extraction_status_enum = sa.Enum('complete', 'incomplete', 'failed', name='extraction_status_enum')
    extraction_status_enum.create(op.get_bind(), checkfirst=True)

    # Add columns to invoices table
    op.add_column('invoices', sa.Column('extraction_status', sa.Enum('complete', 'incomplete', 'failed', name='extraction_status_enum'), nullable=False, server_default='incomplete'))
    op.add_column('invoices', sa.Column('extraction_confidence', sa.Numeric(5, 2), nullable=True))
    op.add_column('invoices', sa.Column('raw_data', sa.dialects.postgresql.JSONB(), nullable=True))

    # Remove shipment_id NOT NULL constraint from invoices
    op.alter_column('invoices', 'shipment_id', nullable=True)

    # Add columns to bill_of_entries table
    op.add_column('bill_of_entries', sa.Column('extraction_status', sa.Enum('complete', 'incomplete', 'failed', name='extraction_status_enum'), nullable=False, server_default='incomplete'))
    op.add_column('bill_of_entries', sa.Column('extraction_confidence', sa.Numeric(5, 2), nullable=True))
    op.add_column('bill_of_entries', sa.Column('raw_data', sa.dialects.postgresql.JSONB(), nullable=True))

    # Remove shipment_id NOT NULL constraint from bill_of_entries
    op.alter_column('bill_of_entries', 'shipment_id', nullable=True)

    # Add columns to packing_lists table
    op.add_column('packing_lists', sa.Column('extraction_status', sa.Enum('complete', 'incomplete', 'failed', name='extraction_status_enum'), nullable=False, server_default='incomplete'))
    op.add_column('packing_lists', sa.Column('extraction_confidence', sa.Numeric(5, 2), nullable=True))
    op.add_column('packing_lists', sa.Column('raw_data', sa.dialects.postgresql.JSONB(), nullable=True))

    # Remove shipment_id NOT NULL constraint from packing_lists
    op.alter_column('packing_lists', 'shipment_id', nullable=True)

    # Add columns to certificates_of_origin table
    op.add_column('certificates_of_origin', sa.Column('extraction_status', sa.Enum('complete', 'incomplete', 'failed', name='extraction_status_enum'), nullable=False, server_default='incomplete'))
    op.add_column('certificates_of_origin', sa.Column('extraction_confidence', sa.Numeric(5, 2), nullable=True))
    op.add_column('certificates_of_origin', sa.Column('raw_data', sa.dialects.postgresql.JSONB(), nullable=True))

    # Remove shipment_id NOT NULL constraint from certificates_of_origin
    op.alter_column('certificates_of_origin', 'shipment_id', nullable=True)

    # Add columns to freight_documents table
    op.add_column('freight_documents', sa.Column('extraction_status', sa.Enum('complete', 'incomplete', 'failed', name='extraction_status_enum'), nullable=False, server_default='incomplete'))
    op.add_column('freight_documents', sa.Column('extraction_confidence', sa.Numeric(5, 2), nullable=True))
    op.add_column('freight_documents', sa.Column('raw_data', sa.dialects.postgresql.JSONB(), nullable=True))

    # Remove shipment_id NOT NULL constraint from freight_documents
    op.alter_column('freight_documents', 'shipment_id', nullable=True)


def downgrade() -> None:
    # Remove columns from freight_documents
    op.drop_column('freight_documents', 'raw_data')
    op.drop_column('freight_documents', 'extraction_confidence')
    op.drop_column('freight_documents', 'extraction_status')
    op.alter_column('freight_documents', 'shipment_id', nullable=False)

    # Remove columns from certificates_of_origin
    op.drop_column('certificates_of_origin', 'raw_data')
    op.drop_column('certificates_of_origin', 'extraction_confidence')
    op.drop_column('certificates_of_origin', 'extraction_status')
    op.alter_column('certificates_of_origin', 'shipment_id', nullable=False)

    # Remove columns from packing_lists
    op.drop_column('packing_lists', 'raw_data')
    op.drop_column('packing_lists', 'extraction_confidence')
    op.drop_column('packing_lists', 'extraction_status')
    op.alter_column('packing_lists', 'shipment_id', nullable=False)

    # Remove columns from bill_of_entries
    op.drop_column('bill_of_entries', 'raw_data')
    op.drop_column('bill_of_entries', 'extraction_confidence')
    op.drop_column('bill_of_entries', 'extraction_status')
    op.alter_column('bill_of_entries', 'shipment_id', nullable=False)

    # Remove columns from invoices
    op.drop_column('invoices', 'raw_data')
    op.drop_column('invoices', 'extraction_confidence')
    op.drop_column('invoices', 'extraction_status')
    op.alter_column('invoices', 'shipment_id', nullable=False)

    # Drop extraction status enum
    extraction_status_enum = sa.Enum('complete', 'incomplete', 'failed', name='extraction_status_enum')
    extraction_status_enum.drop(op.get_bind(), checkfirst=True)
