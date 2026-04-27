"""add_raw_provider_response_to_api_documents

Revision ID: 827b93be2959
Revises: de9d577d1a31
Create Date: 2025-12-18 14:21:11.617931

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '827b93be2959'
down_revision = 'de9d577d1a31'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add raw_provider_response column to api_documents table
    op.add_column(
        'api_documents',
        sa.Column('raw_provider_response', sa.dialects.postgresql.JSONB(astext_type=sa.Text()), nullable=True)
    )


def downgrade() -> None:
    # Remove raw_provider_response column
    op.drop_column('api_documents', 'raw_provider_response')
