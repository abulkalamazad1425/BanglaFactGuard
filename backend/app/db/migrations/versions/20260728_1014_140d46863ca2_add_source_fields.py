revision = "140d46863ca2"
down_revision = "be6f76179d91"
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa


def upgrade() -> None:

    op.add_column(
        "verified_sources",
        sa.Column(
            "display_name_en",
            sa.String(length=255),
            nullable=True,
            comment="English display name",
        ),
    )
    op.add_column(
        "verified_sources",
        sa.Column(
            "search_language",
            sa.String(length=10),
            server_default="bn",
            nullable=False,
            comment="Language for search queries: 'bn' or 'en'",
        ),
    )
    op.add_column(
        "verified_sources",
        sa.Column(
            "js_rendered",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
            comment="Whether the site is JS-rendered (requires Playwright)",
        ),
    )


def downgrade() -> None:

    op.drop_column("verified_sources", "js_rendered")
    op.drop_column("verified_sources", "search_language")
    op.drop_column("verified_sources", "display_name_en")
