"""create prefs table

Revision ID: 0003_prefs
Revises: 0002_routes
Create Date: 2025-01-01 00:00:00.000000

"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "0003_prefs"
down_revision = "0002_routes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "prefs",
        sa.Column("holder_id", sa.Text(), primary_key=True),
        sa.Column("default_preference", postgresql.JSONB(), nullable=False),
        sa.ForeignKeyConstraint(
            ["holder_id"],
            ["holders.token_hash"],
        ),
    )


def downgrade() -> None:
    op.drop_table("prefs")
