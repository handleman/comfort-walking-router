"""prefs timestamps

Revision ID: 0004_prefs_timestamps
Revises: 0003_prefs
Create Date: 2026-11-15 00:00:00.000000

`app/repositories/prefs.py` reads and writes `created_at`/`updated_at`, but
migration 0003 created the table without them — a mismatch that only surfaced
the first time the schema met a live database (2026-11-15). The TTL sweep and
the "prefs persist" rule both need the timestamps, so the schema follows the
repository rather than the other way round.
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0004_prefs_timestamps"
down_revision = "0003_prefs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "prefs",
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
    )
    op.add_column(
        "prefs",
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
    )


def downgrade() -> None:
    op.drop_column("prefs", "updated_at")
    op.drop_column("prefs", "created_at")
