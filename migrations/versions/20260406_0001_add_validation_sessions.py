"""add_validation_sessions_table

Revision ID: a1b2c3d4e5f6
Revises: 827b93be2959
Create Date: 2026-04-06 00:01:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f6'
down_revision = '827b93be2959'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'validation_sessions',
        sa.Column(
            'id',
            postgresql.UUID(as_uuid=False),
            primary_key=True,
            nullable=False,
        ),
        sa.Column('use_case', sa.String(100), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False, server_default='1'),
        sa.Column(
            'workflow_status',
            sa.String(50),
            nullable=False,
            server_default='created',
        ),
        sa.Column(
            'context_data',
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default='{}',
        ),
        sa.Column(
            'shipment_id',
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey('shipments.id', ondelete='SET NULL'),
            nullable=True,
        ),
        sa.Column(
            'created_at',
            sa.DateTime(),
            nullable=False,
            server_default=sa.text('now()'),
        ),
        sa.Column(
            'updated_at',
            sa.DateTime(),
            nullable=False,
            server_default=sa.text('now()'),
        ),
    )

    # Indexes for common query patterns
    op.create_index(
        'ix_validation_sessions_use_case',
        'validation_sessions',
        ['use_case'],
    )
    op.create_index(
        'ix_validation_sessions_workflow_status',
        'validation_sessions',
        ['workflow_status'],
    )
    op.create_index(
        'ix_validation_sessions_shipment_id',
        'validation_sessions',
        ['shipment_id'],
    )


def downgrade() -> None:
    op.drop_index('ix_validation_sessions_shipment_id', table_name='validation_sessions')
    op.drop_index('ix_validation_sessions_workflow_status', table_name='validation_sessions')
    op.drop_index('ix_validation_sessions_use_case', table_name='validation_sessions')
    op.drop_table('validation_sessions')
