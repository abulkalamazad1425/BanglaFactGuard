revision = "31eca564c430"
down_revision = "c64e7a11f599"
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa


def upgrade() -> None:

    op.execute("ALTER TYPE search_provider_enum ADD VALUE IF NOT EXISTS 'SEARXNG'")


def downgrade() -> None:

    pass
