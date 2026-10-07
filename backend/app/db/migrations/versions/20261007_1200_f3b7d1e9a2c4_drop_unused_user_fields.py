"""Drop unused user profile columns and the user_profiles table.

users: bio, phone, avatar_url, is_verified, is_email_verified,
oauth_provider and oauth_subject were never read by any feature (no OAuth
or email-verification flow exists; the settings page no longer edits a
bio/phone/avatar). user_profiles only held a duplicate bio/avatar_url and a
verification_count that was never incremented.

Downgrade recreates the columns/table empty (values are not restorable).

Revision ID: f3b7d1e9a2c4
Revises: e5c9a3f7b1d2
Create Date: 2026-10-07 12:00:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "f3b7d1e9a2c4"
down_revision = "e5c9a3f7b1d2"
branch_labels = None
depends_on = None

_USER_COLUMNS = (
    "bio", "phone", "avatar_url", "is_verified", "is_email_verified", "oauth_provider", "oauth_subject",
)


def upgrade() -> None:
    op.execute("DROP TABLE IF EXISTS user_profiles")
    for column in _USER_COLUMNS:
        op.execute(f"ALTER TABLE users DROP COLUMN IF EXISTS {column}")


def downgrade() -> None:
    op.add_column("users", sa.Column("is_verified", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("users", sa.Column("oauth_provider", sa.String(length=50), nullable=True))
    op.add_column("users", sa.Column("oauth_subject", sa.String(length=255), nullable=True))
    op.add_column("users", sa.Column("avatar_url", sa.String(length=512), nullable=True))
    op.add_column("users", sa.Column("bio", sa.Text(), nullable=True))
    op.add_column("users", sa.Column("phone", sa.String(length=20), nullable=True))
    op.add_column("users", sa.Column("is_email_verified", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.create_table(
        "user_profiles",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("bio", sa.Text(), nullable=True),
        sa.Column("avatar_url", sa.String(length=512), nullable=True),
        sa.Column("verification_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_user_profiles_user_id", "user_profiles", ["user_id"], unique=True)
    op.execute(
        "INSERT INTO user_profiles (id, user_id, verification_count) "
        "SELECT gen_random_uuid(), id, 0 FROM users"
    )
