"""Revocable single-owner hosted sessions."""
from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("owner_sessions",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("expires", sa.Integer(), nullable=False),
        sa.Column("revision", sa.String(), nullable=False),
    )
    op.create_index("ix_owner_sessions_expires", "owner_sessions", ["expires"])


def downgrade():
    raise RuntimeError("Destructive downgrade disabled; restore a verified backup instead")
