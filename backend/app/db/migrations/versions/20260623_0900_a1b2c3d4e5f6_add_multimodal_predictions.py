"""add multimodal_predictions table

Revision ID: a1b2c3d4e5f6
Revises: 2ece7aa03c5b
Create Date: 2026-06-23 09:00:00.000000
"""

# revision identifiers, used by Alembic.
revision = "a1b2c3d4e5f6"
down_revision = "2ece7aa03c5b"
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


def upgrade() -> None:
    op.create_table(
        "multimodal_predictions",
        sa.Column(
            "headline",
            sa.Text(),
            nullable=False,
            comment="User-submitted news headline (stored for display, not used by model)",
        ),
        sa.Column(
            "body_text",
            sa.Text(),
            nullable=False,
            comment="Article body text — the sole text input to the BanglaBERT backbone",
        ),
        sa.Column(
            "minio_object_key",
            sa.String(length=1024),
            nullable=False,
            comment="MinIO object key for the uploaded image (multimodal/{uuid}/{filename})",
        ),
        sa.Column(
            "prediction",
            sa.String(length=20),
            nullable=False,
            comment="Model output label: FAKE or NON_FAKE",
        ),
        sa.Column(
            "confidence_fake",
            sa.Float(),
            nullable=False,
            comment="Softmax probability for the FAKE class (0.0-1.0)",
        ),
        sa.Column(
            "confidence_real",
            sa.Float(),
            nullable=False,
            comment="Softmax probability for the NON_FAKE class (0.0-1.0)",
        ),
        sa.Column(
            "text_embedding",
            postgresql.ARRAY(sa.Float()),
            nullable=False,
            comment="BanglaBERT [CLS] embedding vector (768-dim) for text similarity",
        ),
        sa.Column(
            "image_embedding",
            postgresql.ARRAY(sa.Float()),
            nullable=False,
            comment="EfficientNet-B4 global-pool features (1792-dim) for image similarity",
        ),
        sa.Column(
            "combined_embedding",
            postgresql.ARRAY(sa.Float()),
            nullable=False,
            comment="L2-normalised concat of text+image embeddings (2560-dim); primary dedup key",
        ),
        sa.Column(
            "model_version",
            sa.String(length=100),
            nullable=False,
            comment="Model version tag — deduplication only reuses predictions of the same version",
        ),
        sa.Column(
            "is_duplicate_of_id",
            sa.UUID(),
            sa.ForeignKey("multimodal_predictions.id", ondelete="SET NULL"),
            nullable=True,
            comment="Original prediction UUID if this row was a cache hit; NULL for fresh inference",
        ),
        sa.Column(
            "id",
            sa.UUID(),
            nullable=False,
            comment="Primary key — UUID v4 generated in Python before INSERT",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="Row creation timestamp (UTC, set by DB on INSERT)",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="Row last-update timestamp (UTC, auto-updated by DB on UPDATE)",
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        "ix_multimodal_predictions_created_at",
        "multimodal_predictions",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        "ix_multimodal_predictions_model_version",
        "multimodal_predictions",
        ["model_version"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_multimodal_predictions_model_version", table_name="multimodal_predictions")
    op.drop_index("ix_multimodal_predictions_created_at", table_name="multimodal_predictions")
    op.drop_table("multimodal_predictions")
