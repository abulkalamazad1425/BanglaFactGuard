"""
app/features/multimodal/models.py
====================================
ORM models for the multimodal fact-check feature.

Extends the core verification pipeline to handle:
- Image-based claims (deepfake detection, metadata analysis)
- Video-based claims (keyframe extraction + image analysis)
- Audio-based claims (transcript extraction + text verification)

Tables:
    multimodal_submissions - Tracks each submitted media file
    media_analysis_results - Stores results from individual analysis modules
"""
from __future__ import annotations
from sqlalchemy import String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from app.shared.base_model import Base, TimestampMixin, UUIDMixin

class MultimodalSubmission(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "multimodal_submissions"
    media_type: Mapped[str] = mapped_column(String(20), nullable=False, comment="image | video | audio")
    file_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="pending")
    extracted_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    analysis_results: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

class MediaAnalysisResult(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "media_analysis_results"
    submission_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    analyzer: Mapped[str] = mapped_column(String(100), nullable=False, comment="deepfake_detector | ocr | whisper | etc.")
    result: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    confidence: Mapped[float | None] = mapped_column(nullable=True)
