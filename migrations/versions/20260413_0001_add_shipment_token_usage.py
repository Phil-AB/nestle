"""add_shipment_token_usage_table

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-04-13 00:01:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = 'b2c3d4e5f6a7'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'shipment_token_usage',
        sa.Column(
            'id',
            postgresql.UUID(as_uuid=False),
            primary_key=True,
            nullable=False,
        ),
        sa.Column(
            'shipment_id',
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey('shipments.id', ondelete='SET NULL'),
            nullable=True,
        ),
        # "vendor_validation" | "boe_validation"
        sa.Column('validation_type', sa.String(50), nullable=False),
        # Aggregate token counts
        sa.Column('total_input_tokens', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total_output_tokens', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total_tokens', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('estimated_cost_usd', sa.Numeric(12, 6), nullable=False, server_default='0'),
        sa.Column('call_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('documents_processed', sa.Integer(), nullable=False, server_default='1'),
        # Per-model breakdown list
        sa.Column(
            'by_model',
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        # Full per-call breakdown (optional audit detail)
        sa.Column(
            'breakdown',
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column(
            'created_at',
            sa.DateTime(),
            nullable=False,
            server_default=sa.text('now()'),
        ),
    )

    # Indexes for dashboard queries
    op.create_index(
        'ix_shipment_token_usage_shipment_id',
        'shipment_token_usage',
        ['shipment_id'],
    )
    op.create_index(
        'ix_shipment_token_usage_validation_type',
        'shipment_token_usage',
        ['validation_type'],
    )
    op.create_index(
        'ix_shipment_token_usage_created_at',
        'shipment_token_usage',
        ['created_at'],
    )


def downgrade() -> None:
    op.drop_index('ix_shipment_token_usage_created_at', table_name='shipment_token_usage')
    op.drop_index('ix_shipment_token_usage_validation_type', table_name='shipment_token_usage')
    op.drop_index('ix_shipment_token_usage_shipment_id', table_name='shipment_token_usage')
    op.drop_table('shipment_token_usage')
