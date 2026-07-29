"""processing_step idempotency fields

Adds tool_version, input_checksum and output_bucket to processing_steps so a
completed step fully records its idempotency identity and output location.

Revision ID: b1a2c3d4e5f6
Revises: 43ee54a82153
Create Date: 2026-07-29 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b1a2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "43ee54a82153"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("processing_steps", sa.Column("tool_version", sa.String(), nullable=True))
    op.add_column("processing_steps", sa.Column("input_checksum", sa.String(), nullable=True))
    op.add_column("processing_steps", sa.Column("output_bucket", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("processing_steps", "output_bucket")
    op.drop_column("processing_steps", "input_checksum")
    op.drop_column("processing_steps", "tool_version")
