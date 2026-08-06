"""Cut over to the PDF schema: backfill legacy data into the new tables (reusing
primary keys so existing /verify/{id} and /multimodal/predict/{id} links keep
resolving), repoint verification_logs at submissions, add the multimodal
dedup column, and seed default credibility weight tiers.

Legacy tables (verified_claims, search_queries, retrieved_articles,
verification_results, expert_reviews, credibility_scores,
multimodal_predictions) are left untouched with their data — only read from,
never modified or dropped. verified_sources is not touched at all.
"""

revision = "9ed4fe39e0e9"
down_revision = "9624a66f7531"
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa


def upgrade() -> None:

    # ------------------------------------------------------------------
    # 1. multimodal_analysis.is_duplicate_of_id — documented deviation from
    #    the PDF schema (Table 4.9 has no dedup column); mirrors the existing
    #    multimodal_predictions.is_duplicate_of_id mechanism.
    # ------------------------------------------------------------------
    op.add_column(
        "multimodal_analysis",
        sa.Column(
            "is_duplicate_of_id",
            sa.UUID(),
            nullable=True,
            comment=(
                "Not in DatabaseDescription.pdf Table 4.9 — added because the "
                "PDF's multimodal_analysis has no dedup column, and the live "
                "duplicate-detection feature needs one. Mirrors the legacy "
                "multimodal_predictions.is_duplicate_of_id mechanism."
            ),
        ),
    )
    op.create_foreign_key(
        "multimodal_analysis_is_duplicate_of_id_fkey",
        "multimodal_analysis",
        "multimodal_analysis",
        ["is_duplicate_of_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # ------------------------------------------------------------------
    # 2. Backfill verified_claims -> submissions (same id reused).
    # ------------------------------------------------------------------
    op.execute(
        """
        INSERT INTO submissions (
            id, submission_type, headline, body_text, claimed_source_text,
            claimed_source_id, published_date, submitter_id, content_hash,
            duplicate_of_submission_id, status, is_published, view_count,
            created_at, updated_at
        )
        SELECT
            id, 'SOURCE_BASED'::submission_type_enum, headline, news_body,
            claimed_source, source_id, published_date, submitter_id,
            claim_hash, NULL,
            (CASE status::text
                WHEN 'PENDING' THEN 'PENDING'
                WHEN 'PROCESSING' THEN 'PROCESSING'
                WHEN 'COMPLETED' THEN 'EXPERT_REVIEW'
                WHEN 'FAILED' THEN 'FAILED'
             END)::submission_status_enum,
            false, 0, created_at, updated_at
        FROM verified_claims
        """
    )

    # 3. search_queries -> source_evidence_queries (same enum types, same ids)
    op.execute(
        """
        INSERT INTO source_evidence_queries (
            id, submission_id, query_type, query_text, search_provider,
            results_count, executed_at
        )
        SELECT id, claim_id, query_type, query_text, search_provider,
               results_count, executed_at
        FROM search_queries
        """
    )

    # 4. retrieved_articles -> retrieved_articles_v2 (same ids, so
    #    verification_results.top_article_id keeps resolving in step 5)
    op.execute(
        """
        INSERT INTO retrieved_articles_v2 (
            id, submission_id, url, url_hash, title, body, author,
            published_date, extraction_method, extraction_success,
            rank_score, retrieved_at
        )
        SELECT id, claim_id, url, url_hash, title, body, author,
               published_date, extraction_method, extraction_success,
               rank_score, retrieved_at
        FROM retrieved_articles
        """
    )

    # 5. verification_results -> verification_results_v2 (same ids)
    op.execute(
        """
        INSERT INTO verification_results_v2 (
            id, submission_id, ai_preliminary_label, final_label, confidence,
            reasoning, top_article_id, semantic_similarity, entity_match,
            contradiction_score, keyword_overlap, numerical_consistency,
            avg_verification_time_ms, created_at, updated_at
        )
        SELECT id, claim_id, NULL, label, confidence, reasoning,
               top_article_id, semantic_similarity, entity_match,
               contradiction_score, keyword_overlap, numerical_consistency,
               NULL, created_at, updated_at
        FROM verification_results
        """
    )

    # 6. credibility_scores -> expert_profiles (one-time sync for rows the
    #    dual-write hasn't already covered)
    op.execute(
        """
        INSERT INTO expert_profiles (
            id, user_id, area_of_expertise, credential_notes,
            credibility_score, total_votes, correct_votes,
            completed_reviews_count, is_active, created_at, updated_at
        )
        SELECT gen_random_uuid(), cs.user_id, 'General', NULL, cs.score,
               cs.total_votes, cs.correct_votes, cs.total_votes, true,
               cs.created_at, cs.updated_at
        FROM credibility_scores cs
        WHERE NOT EXISTS (
            SELECT 1 FROM expert_profiles ep WHERE ep.user_id = cs.user_id
        )
        """
    )

    # 7. multimodal_predictions -> submissions (new id) + multimodal_analysis
    #    (same id as multimodal_predictions, so /multimodal/predict/{id}
    #    keeps resolving)
    op.execute(
        """
        WITH mapped AS (
            SELECT mp.id AS old_id, gen_random_uuid() AS new_submission_id,
                   mp.headline, mp.body_text, mp.created_at, mp.updated_at
            FROM multimodal_predictions mp
        ),
        ins_sub AS (
            INSERT INTO submissions (
                id, submission_type, headline, body_text, claimed_source_text,
                claimed_source_id, published_date, submitter_id, content_hash,
                duplicate_of_submission_id, status, is_published, view_count,
                created_at, updated_at
            )
            SELECT new_submission_id, 'MULTIMODAL'::submission_type_enum,
                   headline, body_text, NULL, NULL, NULL, NULL,
                   md5(old_id::text), NULL, 'FINALIZED'::submission_status_enum,
                   false, 0, created_at, updated_at
            FROM mapped
            RETURNING id
        )
        INSERT INTO multimodal_analysis (
            id, submission_id, image_object_key, prediction, confidence_fake,
            confidence_real, text_embedding, image_embedding,
            combined_embedding, model_version, is_duplicate_of_id,
            created_at, updated_at
        )
        SELECT mp.id, m.new_submission_id, mp.minio_object_key,
               mp.prediction::multimodal_prediction_enum, mp.confidence_fake,
               mp.confidence_real, mp.text_embedding, mp.image_embedding,
               mp.combined_embedding, mp.model_version, mp.is_duplicate_of_id,
               mp.created_at, mp.updated_at
        FROM multimodal_predictions mp
        JOIN mapped m ON m.old_id = mp.id
        """
    )

    # ------------------------------------------------------------------
    # 8. Repoint verification_logs at submissions (pipeline-internal
    #    observability table, no PDF counterpart, actively written on every
    #    run — safe to repoint because of the id-preserving backfill above).
    # ------------------------------------------------------------------
    op.drop_constraint(
        "verification_logs_claim_id_fkey", "verification_logs", type_="foreignkey"
    )
    op.alter_column("verification_logs", "claim_id", new_column_name="submission_id")
    op.create_foreign_key(
        "verification_logs_submission_id_fkey",
        "verification_logs",
        "submissions",
        ["submission_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.execute(
        'ALTER INDEX ix_verification_logs_claim_id RENAME TO ix_verification_logs_submission_id'
    )
    op.execute(
        'ALTER INDEX ix_verification_logs_claim_level RENAME TO ix_verification_logs_submission_level'
    )
    op.execute(
        'ALTER INDEX ix_verification_logs_claim_stage RENAME TO ix_verification_logs_submission_stage'
    )

    # ------------------------------------------------------------------
    # 9. Seed default credibility weight tiers so admin-configurable
    #    weighted finalization works without manual setup first.
    # ------------------------------------------------------------------
    op.execute(
        """
        INSERT INTO credibility_weight_tiers
            (id, label, min_accuracy_pct, max_accuracy_pct, weight, is_active,
             created_at, updated_at)
        VALUES
            (gen_random_uuid(), 'Novice', 0.0, 40.0, 0.5, true, now(), now()),
            (gen_random_uuid(), 'Competent', 40.0, 70.0, 1.0, true, now(), now()),
            (gen_random_uuid(), 'Expert', 70.0, 90.0, 1.5, true, now(), now()),
            (gen_random_uuid(), 'Master', 90.0, 100.0, 2.0, true, now(), now())
        """
    )


def downgrade() -> None:

    op.execute(
        "DELETE FROM credibility_weight_tiers WHERE label IN "
        "('Novice', 'Competent', 'Expert', 'Master')"
    )

    op.execute(
        'ALTER INDEX ix_verification_logs_submission_stage RENAME TO ix_verification_logs_claim_stage'
    )
    op.execute(
        'ALTER INDEX ix_verification_logs_submission_level RENAME TO ix_verification_logs_claim_level'
    )
    op.execute(
        'ALTER INDEX ix_verification_logs_submission_id RENAME TO ix_verification_logs_claim_id'
    )
    op.drop_constraint(
        "verification_logs_submission_id_fkey", "verification_logs", type_="foreignkey"
    )
    op.alter_column("verification_logs", "submission_id", new_column_name="claim_id")
    op.create_foreign_key(
        "verification_logs_claim_id_fkey",
        "verification_logs",
        "verified_claims",
        ["claim_id"],
        ["id"],
        ondelete="CASCADE",
    )

    # Delete multimodal-derived submissions, then multimodal_analysis rows
    # backfilled from multimodal_predictions.
    op.execute(
        """
        DELETE FROM submissions
        WHERE id IN (
            SELECT submission_id FROM multimodal_analysis
            WHERE id IN (SELECT id FROM multimodal_predictions)
        )
        """
    )
    op.execute(
        "DELETE FROM multimodal_analysis WHERE id IN (SELECT id FROM multimodal_predictions)"
    )

    op.execute(
        "DELETE FROM expert_profiles WHERE user_id IN (SELECT user_id FROM credibility_scores)"
    )
    op.execute(
        "DELETE FROM verification_results_v2 WHERE id IN (SELECT id FROM verification_results)"
    )
    op.execute(
        "DELETE FROM retrieved_articles_v2 WHERE id IN (SELECT id FROM retrieved_articles)"
    )
    op.execute(
        "DELETE FROM source_evidence_queries WHERE id IN (SELECT id FROM search_queries)"
    )
    op.execute("DELETE FROM submissions WHERE id IN (SELECT id FROM verified_claims)")

    op.drop_constraint(
        "multimodal_analysis_is_duplicate_of_id_fkey",
        "multimodal_analysis",
        type_="foreignkey",
    )
    op.drop_column("multimodal_analysis", "is_duplicate_of_id")
