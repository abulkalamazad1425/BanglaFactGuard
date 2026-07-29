revision = "f89542b9b55a"
down_revision = "3e7f64e4c47d"
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa


def upgrade() -> None:
    op.execute("ALTER TYPE query_type_enum ADD VALUE IF NOT EXISTS 'SITE_RESTRICTED'")


def downgrade() -> None:
    pass
