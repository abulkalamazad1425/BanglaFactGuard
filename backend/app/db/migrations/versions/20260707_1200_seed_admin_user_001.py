from __future__ import annotations

import uuid
from alembic import op
import sqlalchemy as sa

revision = "seed_admin_user_001"
down_revision = "f89542b9b55a"
branch_labels = None
depends_on = None

ADMIN_EMAIL = "admin@gmail.com"

ADMIN_HASHED_PASSWORD = "$2b$12$zkaH4B4BLXDaI5Qh8qrBiuEobgUANmxsmc9xQwVbeXiTFC0xDvfLK"
ADMIN_FULL_NAME = "System Administrator"
ADMIN_ID = str(uuid.uuid4())


def upgrade() -> None:

    conn = op.get_bind()
    existing = conn.execute(
        sa.text("SELECT id FROM users WHERE email = :email"),
        {"email": ADMIN_EMAIL},
    ).fetchone()

    if existing is None:
        conn.execute(
            sa.text("""
                INSERT INTO users (id, email, hashed_password, full_name, role,
                                   is_active, is_verified,
                                   created_at, updated_at)
                VALUES (:id, :email, :hashed_password, :full_name, 'admin',
                        TRUE, TRUE,
                        NOW(), NOW())
            """),
            {
                "id": ADMIN_ID,
                "email": ADMIN_EMAIL,
                "hashed_password": ADMIN_HASHED_PASSWORD,
                "full_name": ADMIN_FULL_NAME,
            },
        )


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        sa.text("DELETE FROM users WHERE email = :email"),
        {"email": ADMIN_EMAIL},
    )
