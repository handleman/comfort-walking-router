"""create routes table

Revision ID: 0002_routes
Revises: 0001_holders
Create Date: 2025-01-01 00:00:00.000000

"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "0002_routes"
down_revision = "0001_holders"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "routes",
        sa.Column("id", postgresql.UUID(), primary_key=True),
        sa.Column(
            "holder_id",
            sa.Text(),
            nullable=False,
        ),
        sa.Column("request", postgresql.JSONB(), nullable=False),
        sa.Column("response", postgresql.JSONB(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "last_accessed_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.ForeignKeyConstraint(
            ["holder_id"],
            ["holders.token_hash"],
        ),
    )


def downgrade() -> None:
    op.drop_table("routes")
