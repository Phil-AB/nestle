"""add boe_number to shipments

Revision ID: 20260419_0001
Revises:
Create Date: 2026-04-19

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers
revision = '20260419_0001_add_boe_number'
down_revision = 'b2c3d4e5f6a7'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'shipments',
        sa.Column('boe_number', sa.String(100), nullable=True),
    )
    op.create_index('ix_shipments_boe_number', 'shipments', ['boe_number'], unique=True)


def downgrade() -> None:
    op.drop_index('ix_shipments_boe_number', table_name='shipments')
    op.drop_column('shipments', 'boe_number')
