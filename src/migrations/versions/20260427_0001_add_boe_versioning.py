"""Add BOE versioning: boe_version column and shipment_boe_history table

Revision ID: 20260427_0001
Revises: 20260419_0001_add_boe_number_to_shipments
Create Date: 2026-04-27
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision = "20260427_0001"
down_revision = "20260419_0001_add_boe_number"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "shipments",
        sa.Column("boe_version", sa.Integer(), nullable=False, server_default="0"),
    )

    op.create_table(
        "shipment_boe_history",
        sa.Column("id", UUID(as_uuid=False), primary_key=True),
        sa.Column(
            "shipment_id",
            UUID(as_uuid=False),
            sa.ForeignKey("shipments.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("boe_number", sa.String(100), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("validated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("extracted_fields", JSONB(), nullable=True),
    )

    op.create_index("ix_shipment_boe_history_shipment_id", "shipment_boe_history", ["shipment_id"])
    op.create_index(
        "ix_shipment_boe_history_shipment_version",
        "shipment_boe_history",
        ["shipment_id", "version"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_table("shipment_boe_history")
    op.drop_column("shipments", "boe_version")
