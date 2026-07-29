from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "2ece7aa03c5b"
down_revision = "c8bfea04d45d"
branch_labels = None
depends_on = None


def upgrade() -> None:

    op.rename_table("source_registry", "verified_sources")

    op.execute(
        "ALTER INDEX IF EXISTS ix_source_registry_aliases_gin RENAME TO ix_verified_sources_aliases_gin"
    )
    op.execute(
        "ALTER INDEX IF EXISTS ix_source_registry_canonical_name RENAME TO ix_verified_sources_canonical_name"
    )
    op.execute(
        "ALTER INDEX IF EXISTS ix_source_registry_created_at RENAME TO ix_verified_sources_created_at"
    )
    op.execute(
        "ALTER INDEX IF EXISTS ix_source_registry_is_active RENAME TO ix_verified_sources_is_active"
    )
    op.execute(
        "ALTER INDEX IF EXISTS ix_source_registry_language_active RENAME TO ix_verified_sources_language_active"
    )

    op.add_column(
        "verified_sources",
        sa.Column(
            "body_selectors", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
    )
    op.add_column(
        "verified_sources",
        sa.Column(
            "title_selectors", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
    )
    op.add_column(
        "verified_sources",
        sa.Column(
            "date_selectors", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
    )
    op.add_column(
        "verified_sources",
        sa.Column("internal_search_url", sa.String(length=512), nullable=True),
    )
    op.add_column(
        "verified_sources",
        sa.Column(
            "article_url_patterns",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )

    op.drop_constraint(
        "verified_claims_source_id_fkey", "verified_claims", type_="foreignkey"
    )
    op.create_foreign_key(
        "verified_claims_source_id_fkey",
        "verified_claims",
        "verified_sources",
        ["source_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:

    op.drop_column("verified_sources", "article_url_patterns")
    op.drop_column("verified_sources", "internal_search_url")
    op.drop_column("verified_sources", "date_selectors")
    op.drop_column("verified_sources", "title_selectors")
    op.drop_column("verified_sources", "body_selectors")

    op.rename_table("verified_sources", "source_registry")

    op.execute(
        "ALTER INDEX IF EXISTS ix_verified_sources_aliases_gin RENAME TO ix_source_registry_aliases_gin"
    )
    op.execute(
        "ALTER INDEX IF EXISTS ix_verified_sources_canonical_name RENAME TO ix_source_registry_canonical_name"
    )
    op.execute(
        "ALTER INDEX IF EXISTS ix_verified_sources_created_at RENAME TO ix_source_registry_created_at"
    )
    op.execute(
        "ALTER INDEX IF EXISTS ix_verified_sources_is_active RENAME TO ix_source_registry_is_active"
    )
    op.execute(
        "ALTER INDEX IF EXISTS ix_verified_sources_language_active RENAME TO ix_source_registry_language_active"
    )

    op.drop_constraint(
        "verified_claims_source_id_fkey", "verified_claims", type_="foreignkey"
    )
    op.create_foreign_key(
        "verified_claims_source_id_fkey",
        "verified_claims",
        "source_registry",
        ["source_id"],
        ["id"],
        ondelete="SET NULL",
    )
