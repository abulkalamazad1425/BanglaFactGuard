"""
app/models/verification_log.py
================================
ORM model for the `verification_logs` table.

Append-only audit table that records every significant event emitted by each
pipeline stage during a verification run. Unlike application logs (which go to
stdout/file), these records are queryable via SQL — enabling post-hoc analysis
of pipeline failures, slow stages, and error patterns.

Design decisions:
- Intentionally write-once (no updated_at) to preserve audit integrity.
- `metadata_` is stored as JSONB to accommodate stage-specific debug payloads
  (e.g. query strings, extraction errors, score breakdowns) without schema churn.
- `duration_ms` enables stage-level performance profiling in SQL.

Relationships:
    verification_logs → verified_claims  (many-to-one)
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.constants import LogLevel, PipelineStageID
from app.models.base import Base, ReprMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.verified_claim import VerifiedClaim


class VerificationLog(UUIDMixin, ReprMixin, Base):
    """
    Single audit log entry for one event within a pipeline stage.

    Attributes:
        claim_id:    FK to the parent verified_claim.
        stage:       Pipeline stage that emitted this log (S01–S12 enum).
        level:       Severity: INFO | WARNING | ERROR.
        message:     Short human-readable event description.
        metadata_:   JSONB blob with stage-specific debug data (GIN-indexed).
        duration_ms: How long the stage took up to this log point (ms).
        created_at:  Timestamp of the log entry (UTC).
    """

    __tablename__ = "verification_logs"

    # --- Core fields --------------------------------------------------------

    claim_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("verified_claims.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="FK to verified_claims — the claim this log entry belongs to",
    )

    stage: Mapped[PipelineStageID] = mapped_column(
        Enum(PipelineStageID, name="pipeline_stage_id_enum", create_type=True),
        nullable=False,
        index=True,
        comment="Pipeline stage that emitted this log: s01_normalizer … s12_persistence",
    )

    level: Mapped[LogLevel] = mapped_column(
        Enum(LogLevel, name="log_level_enum", create_type=True),
        nullable=False,
        index=True,
        comment="Log severity: INFO | WARNING | ERROR",
    )

    message: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Short human-readable description of the logged event",
    )

    metadata_: Mapped[dict | None] = mapped_column(
        "metadata",      # Column name in DB is 'metadata'; Python attr is metadata_
        JSONB,
        nullable=True,
        default=dict,
        comment="Stage-specific debug payload as JSONB (e.g. query text, error message, scores)",
    )

    duration_ms: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Milliseconds elapsed in the stage up to this log point",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
        comment="Log entry timestamp (UTC)",
    )

    # --- Relationships ------------------------------------------------------

    claim: Mapped["VerifiedClaim"] = relationship(
        "VerifiedClaim",
        back_populates="logs",
        lazy="select",
    )

    # --- Composite indexes --------------------------------------------------

    __table_args__ = (
        Index("ix_verification_logs_claim_stage", claim_id, stage),
        Index("ix_verification_logs_claim_level", claim_id, level),
        Index("ix_verification_logs_stage_level", stage, level),
        # GIN index on metadata for JSON containment queries:
        # WHERE metadata @> '{"provider": "brave"}'
        Index(
            "ix_verification_logs_metadata_gin",
            metadata_,
            postgresql_using="gin",
        ),
    )
