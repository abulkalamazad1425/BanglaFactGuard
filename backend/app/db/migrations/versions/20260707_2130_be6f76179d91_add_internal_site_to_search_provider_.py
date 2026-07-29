revision = "be6f76179d91"
down_revision = "seed_admin_user_001"
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa


def upgrade() -> None:

    op.execute(
        "ALTER TYPE search_provider_enum ADD VALUE IF NOT EXISTS 'INTERNAL_SITE'"
    )


def downgrade() -> None:
    pass
