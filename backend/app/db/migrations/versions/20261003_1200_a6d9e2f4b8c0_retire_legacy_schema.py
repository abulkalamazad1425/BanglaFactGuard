"""Retire the legacy claim schema and use canonical submission table names.

No writes or schema changes to verified_sources or credibility_weight_tiers.
Destructive legacy-table removal requires a restorable backup. Operational
data reset is a separate, explicit maintenance operation, not a startup task.
"""

from alembic import op
import sqlalchemy as sa

revision = "a6d9e2f4b8c0"
down_revision = "d1a7c3e5f9b2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for table in (
        "user_feedback", "audit_log", "verification_logs",
        "verification_results", "expert_reviews", "search_queries",
        "retrieved_articles", "verified_claims", "credibility_scores",
        "multimodal_predictions",
    ):
        # Deliberately no CASCADE: unexpected external dependencies must stop us.
        op.drop_table(table)

    connection = op.get_bind()
    quote = connection.dialect.identifier_preparer.quote
    for old in ("retrieved_articles_v2", "verification_results_v2", "expert_reviews_v2"):
        new = old.removesuffix("_v2")
        op.rename_table(old, new)
        # Constraint-backed indexes are renamed with their constraints first.
        constraints = connection.execute(sa.text(
            "SELECT conname FROM pg_constraint WHERE conrelid = to_regclass(:table)"
        ), {"table": new}).scalars().all()
        for name in constraints:
            if old in name:
                connection.exec_driver_sql(
                    f"ALTER TABLE {quote(new)} RENAME CONSTRAINT {quote(name)} "
                    f"TO {quote(name.replace(old, new))}"
                )
        indexes = connection.execute(sa.text(
            "SELECT indexname FROM pg_indexes WHERE schemaname = current_schema() "
            "AND tablename = :table"
        ), {"table": new}).scalars().all()
        for name in indexes:
            if old in name:
                connection.exec_driver_sql(
                    f"ALTER INDEX {quote(name)} RENAME TO {quote(name.replace(old, new))}"
                )


def downgrade() -> None:
    raise RuntimeError("Legacy data cannot be reconstructed; restore the pre-cleanup backup.")
