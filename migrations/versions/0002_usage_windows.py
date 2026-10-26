"""Shared mutation and AI request budgets."""
from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "usage_windows",
        sa.Column("key", sa.String(), primary_key=True),
        sa.Column("used", sa.Integer(), nullable=False),
        sa.Column("expires", sa.Integer(), nullable=False),
    )
    op.create_index("ix_usage_windows_expires", "usage_windows", ["expires"])


def downgrade():
    raise RuntimeError("Destructive downgrade disabled; restore a verified backup instead")
