
revision = 'c8bfea04d45d'
down_revision = '31eca564c430'
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa


def upgrade() -> None:

    op.execute("ALTER TYPE search_provider_enum ADD VALUE IF NOT EXISTS 'NEWSDATA'")
    op.execute("ALTER TYPE search_provider_enum ADD VALUE IF NOT EXISTS 'GOOGLE_CUSTOM_SEARCH'")
    op.execute("ALTER TYPE search_provider_enum ADD VALUE IF NOT EXISTS 'PY_GOOGLE_NEWS'")


def downgrade() -> None:
    pass
