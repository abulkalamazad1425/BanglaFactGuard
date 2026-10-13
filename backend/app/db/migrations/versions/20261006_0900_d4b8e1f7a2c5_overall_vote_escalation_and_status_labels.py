from __future__ import annotations

import json
import re
import unicodedata

import sqlalchemy as sa
from alembic import op

revision = "d4b8e1f7a2c5"
down_revision = "c7e2a9d4f1b3"
branch_labels = None
depends_on = None

_GENERIC_BODY = "Your automatic check is complete. View your result."
_ZERO_WIDTH_RE = re.compile("[​⁠﻿]")
_TRAILING_TERMINATOR_RE = re.compile(r"\s*[।.!?]$")


def _exact_key(text: str) -> str:
    t = unicodedata.normalize("NFC", text or "")
    t = _ZERO_WIDTH_RE.sub("", t)
    t = re.sub(r"\s+", " ", t).strip()
    return _TRAILING_TERMINATOR_RE.sub("", t).strip()


def _preview(headline: str | None) -> str:
    tokens = unicodedata.normalize("NFC", headline or "").split()
    text = " ".join(tokens[:5])
    return (f"{text}..." if len(tokens) > 5 else text) or "Your submitted claim"


def _backfill_exact_match(bind) -> None:
    rows = bind.execute(
        sa.text(
            """
            SELECT vr.id, vr.analysis_details, s.headline, ra.title
            FROM verification_results vr
            JOIN submissions s ON s.id = vr.submission_id
            LEFT JOIN retrieved_articles ra ON ra.id = vr.top_article_id
            WHERE vr.content_status = 'MATCHED' AND vr.headline_exact_match IS NULL
            """
        )
    ).fetchall()
    for row_id, analysis, headline, article_title in rows:
        if isinstance(analysis, str):
            try:
                analysis = json.loads(analysis)
            except ValueError:
                analysis = None
        detail = (analysis or {}).get("headline_alteration") or {}
        if detail.get("basis") == "exact" or detail.get("exact_match") is True:
            exact = True
        else:
            claim = detail.get("claim_headline") or headline
            title = detail.get("source_title") or article_title
            if not claim or not title:
                continue
            key = _exact_key(claim)
            exact = bool(key) and key == _exact_key(title)
        bind.execute(
            sa.text("UPDATE verification_results SET headline_exact_match = :v WHERE id = :id"),
            {"v": exact, "id": row_id},
        )


def _rewrite_generic_notifications(bind) -> None:
    rows = bind.execute(
        sa.text(
            """
            SELECT n.id, s.headline
            FROM notifications n
            JOIN submissions s ON n.link_url = '/verify/' || CAST(s.id AS TEXT)
            WHERE n.body = :generic
            """
        ),
        {"generic": _GENERIC_BODY},
    ).fetchall()
    for notification_id, headline in rows:
        bind.execute(
            sa.text("UPDATE notifications SET body = :body WHERE id = :id"),
            {"body": _preview(headline), "id": notification_id},
        )


def upgrade() -> None:
    op.drop_column("voting_config", "max_tier_weight")
    op.add_column(
        "expert_reviews",
        sa.Column(
            "is_admin_decision",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
            comment=(
                "True for the administrator's decision on an ESCALATED claim. That "
                "overall vote IS the final verdict; earlier expert votes cannot "
                "override it."
            ),
        ),
    )
    op.add_column(
        "submissions",
        sa.Column(
            "escalated_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="When expert review escalated this claim to admin review (NULL otherwise).",
        ),
    )
    op.execute("UPDATE submissions SET escalated_at = updated_at WHERE status = 'ESCALATED'")

    bind = op.get_bind()
    _backfill_exact_match(bind)
    _rewrite_generic_notifications(bind)


def downgrade() -> None:
    op.drop_column("submissions", "escalated_at")
    op.drop_column("expert_reviews", "is_admin_decision")
    op.add_column(
        "voting_config",
        sa.Column(
            "max_tier_weight",
            sa.Float(),
            nullable=True,
            comment="Upper bound on any credibility_weight_tiers.weight value (NULL = no cap)",
        ),
    )
