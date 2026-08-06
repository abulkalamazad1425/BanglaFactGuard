"""Add DatabaseDescription.pdf schema — submissions, source_evidence_queries,
retrieved_articles_v2, ocr_extractions, multimodal_analysis, verification_results_v2,
credibility_weight_tiers, expert_profiles, expert_reviews_v2, and additive columns
on users.

Additive-only migration: every table here is new. The `_v2` suffix on
retrieved_articles/verification_results/expert_reviews avoids colliding with the
legacy tables of the same (unsuffixed) name, which the live verification pipeline
keeps using untouched. Nothing in `verified_sources` is touched by this migration.
"""

revision = "9624a66f7531"
down_revision = "140d46863ca2"
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


def upgrade() -> None:
    op.create_table('credibility_weight_tiers',
    sa.Column('label', sa.String(length=100), nullable=False),
    sa.Column('min_accuracy_pct', sa.Float(), nullable=False),
    sa.Column('max_accuracy_pct', sa.Float(), nullable=False),
    sa.Column('weight', sa.Float(), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('id', sa.UUID(), nullable=False, comment='Primary key — UUID v4 generated in Python before INSERT'),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False, comment='Row creation timestamp (UTC, set by DB on INSERT)'),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False, comment='Row last-update timestamp (UTC, auto-updated by DB on UPDATE)'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_credibility_weight_tiers_created_at'), 'credibility_weight_tiers', ['created_at'], unique=False)
    op.create_table('expert_profiles',
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('area_of_expertise', sa.String(length=255), nullable=False),
    sa.Column('credential_notes', sa.Text(), nullable=True),
    sa.Column('credibility_score', sa.Float(), nullable=False),
    sa.Column('total_votes', sa.Integer(), nullable=False),
    sa.Column('correct_votes', sa.Integer(), nullable=False),
    sa.Column('completed_reviews_count', sa.Integer(), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('id', sa.UUID(), nullable=False, comment='Primary key — UUID v4 generated in Python before INSERT'),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False, comment='Row creation timestamp (UTC, set by DB on INSERT)'),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False, comment='Row last-update timestamp (UTC, auto-updated by DB on UPDATE)'),
    sa.CheckConstraint('credibility_score >= 0.0 AND credibility_score <= 1.0', name='ck_expert_profiles_credibility_score_range'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_expert_profiles_created_at'), 'expert_profiles', ['created_at'], unique=False)
    op.create_index(op.f('ix_expert_profiles_user_id'), 'expert_profiles', ['user_id'], unique=True)
    op.create_table('submissions',
    sa.Column('submission_type', sa.Enum('MULTIMODAL', 'SOURCE_BASED', 'PHOTO_CARD', name='submission_type_enum'), nullable=False, comment='MULTIMODAL | SOURCE_BASED | PHOTO_CARD'),
    sa.Column('headline', sa.Text(), nullable=True),
    sa.Column('body_text', sa.Text(), nullable=True),
    sa.Column('claimed_source_text', sa.String(length=255), nullable=True, comment='Raw source string as provided by the user'),
    sa.Column('claimed_source_id', sa.UUID(), nullable=True),
    sa.Column('published_date', sa.Date(), nullable=True),
    sa.Column('submitter_id', sa.UUID(), nullable=True),
    sa.Column('content_hash', sa.String(length=64), nullable=False, comment='SHA-256 hex of normalised submission content — dedup key'),
    sa.Column('duplicate_of_submission_id', sa.UUID(), nullable=True, comment='Self-referential FK — set when this submission is a duplicate of another'),
    sa.Column('status', sa.Enum('PENDING', 'PROCESSING', 'EXPERT_REVIEW', 'FINALIZED', 'FAILED', name='submission_status_enum'), nullable=False),
    sa.Column('is_published', sa.Boolean(), nullable=False),
    sa.Column('view_count', sa.Integer(), nullable=False),
    sa.Column('id', sa.UUID(), nullable=False, comment='Primary key — UUID v4 generated in Python before INSERT'),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False, comment='Row creation timestamp (UTC, set by DB on INSERT)'),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False, comment='Row last-update timestamp (UTC, auto-updated by DB on UPDATE)'),
    sa.ForeignKeyConstraint(['claimed_source_id'], ['verified_sources.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['duplicate_of_submission_id'], ['submissions.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['submitter_id'], ['users.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_submissions_claimed_source_id'), 'submissions', ['claimed_source_id'], unique=False)
    op.create_index(op.f('ix_submissions_content_hash'), 'submissions', ['content_hash'], unique=False)
    op.create_index(op.f('ix_submissions_created_at'), 'submissions', ['created_at'], unique=False)
    op.create_index(op.f('ix_submissions_status'), 'submissions', ['status'], unique=False)
    op.create_index('ix_submissions_status_created', 'submissions', ['status', 'created_at'], unique=False)
    op.create_index(op.f('ix_submissions_submission_type'), 'submissions', ['submission_type'], unique=False)
    op.create_index(op.f('ix_submissions_submitter_id'), 'submissions', ['submitter_id'], unique=False)
    op.create_table('expert_reviews_v2',
    sa.Column('submission_id', sa.UUID(), nullable=False),
    sa.Column('reviewer_id', sa.UUID(), nullable=True),
    sa.Column('ai_label', sa.String(length=20), nullable=False),
    sa.Column('expert_label', postgresql.ENUM('TRUE', 'FALSE', 'PARTIALLY_TRUE', 'NOT_FOUND_IN_CLAIMED_SOURCE', name='verification_label_enum', create_type=False), nullable=False),
    sa.Column('justification', sa.Text(), nullable=True),
    sa.Column('credibility_weight', sa.Float(), nullable=False),
    sa.Column('applied_weight_tier_id', sa.UUID(), nullable=True),
    sa.Column('status', sa.String(length=50), nullable=False),
    sa.Column('id', sa.UUID(), nullable=False, comment='Primary key — UUID v4 generated in Python before INSERT'),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False, comment='Row creation timestamp (UTC, set by DB on INSERT)'),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False, comment='Row last-update timestamp (UTC, auto-updated by DB on UPDATE)'),
    sa.ForeignKeyConstraint(['applied_weight_tier_id'], ['credibility_weight_tiers.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['reviewer_id'], ['users.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['submission_id'], ['submissions.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_expert_reviews_v2_created_at'), 'expert_reviews_v2', ['created_at'], unique=False)
    op.create_index(op.f('ix_expert_reviews_v2_reviewer_id'), 'expert_reviews_v2', ['reviewer_id'], unique=False)
    op.create_index(op.f('ix_expert_reviews_v2_status'), 'expert_reviews_v2', ['status'], unique=False)
    op.create_index(op.f('ix_expert_reviews_v2_submission_id'), 'expert_reviews_v2', ['submission_id'], unique=False)
    op.create_table('multimodal_analysis',
    sa.Column('submission_id', sa.UUID(), nullable=False),
    sa.Column('image_object_key', sa.String(length=1024), nullable=False),
    sa.Column('prediction', sa.Enum('FAKE', 'NON_FAKE', name='multimodal_prediction_enum'), nullable=False),
    sa.Column('confidence_fake', sa.Float(), nullable=False),
    sa.Column('confidence_real', sa.Float(), nullable=False),
    sa.Column('text_embedding', sa.ARRAY(sa.Float()), nullable=True, comment='BanglaBERT [CLS] embedding vector (768-dim)'),
    sa.Column('image_embedding', sa.ARRAY(sa.Float()), nullable=True, comment='EfficientNet-B4 global-pool features (1792-dim)'),
    sa.Column('combined_embedding', sa.ARRAY(sa.Float()), nullable=True, comment='L2-normalised concat of text+image embeddings (2560-dim)'),
    sa.Column('model_version', sa.String(length=100), nullable=False),
    sa.Column('id', sa.UUID(), nullable=False, comment='Primary key — UUID v4 generated in Python before INSERT'),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False, comment='Row creation timestamp (UTC, set by DB on INSERT)'),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False, comment='Row last-update timestamp (UTC, auto-updated by DB on UPDATE)'),
    sa.CheckConstraint('confidence_fake >= 0.0 AND confidence_fake <= 1.0', name='ck_multimodal_analysis_confidence_fake_range'),
    sa.CheckConstraint('confidence_real >= 0.0 AND confidence_real <= 1.0', name='ck_multimodal_analysis_confidence_real_range'),
    sa.ForeignKeyConstraint(['submission_id'], ['submissions.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_multimodal_analysis_created_at'), 'multimodal_analysis', ['created_at'], unique=False)
    op.create_index(op.f('ix_multimodal_analysis_model_version'), 'multimodal_analysis', ['model_version'], unique=False)
    op.create_index(op.f('ix_multimodal_analysis_submission_id'), 'multimodal_analysis', ['submission_id'], unique=True)
    op.create_table('ocr_extractions',
    sa.Column('submission_id', sa.UUID(), nullable=False),
    sa.Column('image_object_key', sa.String(length=1024), nullable=False),
    sa.Column('raw_extracted_text', sa.Text(), nullable=False),
    sa.Column('confirmed_text', sa.Text(), nullable=True),
    sa.Column('ocr_confidence', sa.Float(), nullable=True),
    sa.Column('ocr_engine', sa.String(length=100), nullable=False),
    sa.Column('is_confirmed', sa.Boolean(), nullable=False),
    sa.Column('id', sa.UUID(), nullable=False, comment='Primary key — UUID v4 generated in Python before INSERT'),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False, comment='Row creation timestamp (UTC, set by DB on INSERT)'),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False, comment='Row last-update timestamp (UTC, auto-updated by DB on UPDATE)'),
    sa.CheckConstraint('ocr_confidence IS NULL OR (ocr_confidence >= 0.0 AND ocr_confidence <= 1.0)', name='ck_ocr_extractions_confidence_range'),
    sa.ForeignKeyConstraint(['submission_id'], ['submissions.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_ocr_extractions_created_at'), 'ocr_extractions', ['created_at'], unique=False)
    op.create_index(op.f('ix_ocr_extractions_submission_id'), 'ocr_extractions', ['submission_id'], unique=True)
    op.create_table('retrieved_articles_v2',
    sa.Column('submission_id', sa.UUID(), nullable=False),
    sa.Column('url', sa.Text(), nullable=False),
    sa.Column('url_hash', sa.String(length=64), nullable=False),
    sa.Column('title', sa.Text(), nullable=True),
    sa.Column('body', sa.Text(), nullable=True),
    sa.Column('author', sa.String(length=255), nullable=True),
    sa.Column('published_date', sa.Date(), nullable=True),
    sa.Column('extraction_method', postgresql.ENUM('JSON_LD', 'OPENGRAPH', 'SOURCE_SPECIFIC', 'TRAFILATURA', 'READABILITY', 'BEAUTIFULSOUP', name='extraction_method_enum', create_type=False), nullable=True),
    sa.Column('extraction_success', sa.Boolean(), nullable=False),
    sa.Column('rank_score', sa.Float(), nullable=True),
    sa.Column('retrieved_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('id', sa.UUID(), nullable=False, comment='Primary key — UUID v4 generated in Python before INSERT'),
    sa.CheckConstraint('rank_score IS NULL OR (rank_score >= 0.0 AND rank_score <= 1.0)', name='ck_retrieved_articles_v2_rank_score_range'),
    sa.ForeignKeyConstraint(['submission_id'], ['submissions.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_retrieved_articles_v2_extraction_success'), 'retrieved_articles_v2', ['extraction_success'], unique=False)
    op.create_index(op.f('ix_retrieved_articles_v2_rank_score'), 'retrieved_articles_v2', ['rank_score'], unique=False)
    op.create_index(op.f('ix_retrieved_articles_v2_submission_id'), 'retrieved_articles_v2', ['submission_id'], unique=False)
    op.create_index('uq_retrieved_articles_v2_submission_url_hash', 'retrieved_articles_v2', ['submission_id', 'url_hash'], unique=True)
    op.create_table('source_evidence_queries',
    sa.Column('submission_id', sa.UUID(), nullable=False),
    sa.Column('query_type', postgresql.ENUM('HEADLINE', 'KEYWORDS', 'ENTITIES', 'DATE_BOUND', 'BODY_SUMMARY', 'SITE_RESTRICTED', name='query_type_enum', create_type=False), nullable=False),
    sa.Column('query_text', sa.Text(), nullable=False),
    sa.Column('search_provider', postgresql.ENUM('INTERNAL_SITE', 'NEWSDATA', 'GOOGLE_CUSTOM_SEARCH', 'PY_GOOGLE_NEWS', 'SEARXNG', 'GOOGLE_RSS', 'DDG', 'BRAVE', name='search_provider_enum', create_type=False), nullable=False),
    sa.Column('results_count', sa.Integer(), nullable=False),
    sa.Column('executed_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('id', sa.UUID(), nullable=False, comment='Primary key — UUID v4 generated in Python before INSERT'),
    sa.ForeignKeyConstraint(['submission_id'], ['submissions.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_source_evidence_queries_executed_at'), 'source_evidence_queries', ['executed_at'], unique=False)
    op.create_index(op.f('ix_source_evidence_queries_search_provider'), 'source_evidence_queries', ['search_provider'], unique=False)
    op.create_index(op.f('ix_source_evidence_queries_submission_id'), 'source_evidence_queries', ['submission_id'], unique=False)
    op.create_index('ix_source_evidence_queries_submission_provider', 'source_evidence_queries', ['submission_id', 'search_provider'], unique=False)
    op.create_table('verification_results_v2',
    sa.Column('submission_id', sa.UUID(), nullable=False),
    sa.Column('ai_preliminary_label', sa.String(length=20), nullable=True),
    sa.Column('final_label', postgresql.ENUM('TRUE', 'FALSE', 'PARTIALLY_TRUE', 'NOT_FOUND_IN_CLAIMED_SOURCE', name='verification_label_enum', create_type=False), nullable=True),
    sa.Column('confidence', sa.Float(), nullable=True),
    sa.Column('reasoning', sa.Text(), nullable=True),
    sa.Column('top_article_id', sa.UUID(), nullable=True),
    sa.Column('semantic_similarity', sa.Float(), nullable=True),
    sa.Column('entity_match', sa.Float(), nullable=True),
    sa.Column('contradiction_score', sa.Float(), nullable=True),
    sa.Column('keyword_overlap', sa.Float(), nullable=True),
    sa.Column('numerical_consistency', sa.Float(), nullable=True),
    sa.Column('avg_verification_time_ms', sa.Integer(), nullable=True),
    sa.Column('id', sa.UUID(), nullable=False, comment='Primary key — UUID v4 generated in Python before INSERT'),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False, comment='Row creation timestamp (UTC, set by DB on INSERT)'),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False, comment='Row last-update timestamp (UTC, auto-updated by DB on UPDATE)'),
    sa.CheckConstraint('confidence IS NULL OR (confidence >= 0.0 AND confidence <= 1.0)', name='ck_verification_results_v2_confidence_range'),
    sa.CheckConstraint('contradiction_score IS NULL OR (contradiction_score >= 0.0 AND contradiction_score <= 1.0)', name='ck_verification_results_v2_contradiction_score_range'),
    sa.CheckConstraint('semantic_similarity IS NULL OR (semantic_similarity >= 0.0 AND semantic_similarity <= 1.0)', name='ck_verification_results_v2_semantic_similarity_range'),
    sa.ForeignKeyConstraint(['submission_id'], ['submissions.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['top_article_id'], ['retrieved_articles_v2.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_verification_results_v2_created_at'), 'verification_results_v2', ['created_at'], unique=False)
    op.create_index(op.f('ix_verification_results_v2_final_label'), 'verification_results_v2', ['final_label'], unique=False)
    op.create_index('ix_verification_results_v2_label_created', 'verification_results_v2', ['final_label', 'created_at'], unique=False)
    op.create_index(op.f('ix_verification_results_v2_submission_id'), 'verification_results_v2', ['submission_id'], unique=True)
    op.add_column('users', sa.Column('avatar_url', sa.String(length=512), nullable=True, comment='DatabaseDescription.pdf Table 4.1 — profile picture URL'))
    op.add_column('users', sa.Column('bio', sa.Text(), nullable=True, comment='DatabaseDescription.pdf Table 4.1 — free-text profile bio'))
    op.add_column('users', sa.Column('phone', sa.String(length=20), nullable=True, comment='DatabaseDescription.pdf Table 4.1 — contact phone number'))
    op.add_column('users', sa.Column('total_submissions', sa.Integer(), server_default=sa.text('0'), nullable=False, comment='DatabaseDescription.pdf Table 4.1 — cached submission counter'))
    op.add_column('users', sa.Column('is_email_verified', sa.Boolean(), server_default=sa.text('false'), nullable=False, comment='DatabaseDescription.pdf Table 4.1 — additive column, kept separate from the pre-existing `is_verified` column, which auth flows still read/write unchanged'))
    op.create_check_constraint(
        "ck_users_role_valid", "users", "role IN ('user', 'expert', 'admin')"
    )
    # NOTE: autogenerate also proposed dropping the server_default on
    # verified_sources.search_language / verified_sources.js_rendered (pre-existing
    # drift between the ORM's client-side `default=` and the DB's server_default from
    # migration 140d46863ca2 — unrelated to this change). verified_sources must not be
    # touched by this migration, so those two op.alter_column calls were removed.


def downgrade() -> None:
    op.drop_constraint("ck_users_role_valid", "users", type_="check")
    op.drop_column('users', 'is_email_verified')
    op.drop_column('users', 'total_submissions')
    op.drop_column('users', 'phone')
    op.drop_column('users', 'bio')
    op.drop_column('users', 'avatar_url')
    op.drop_index(op.f('ix_verification_results_v2_submission_id'), table_name='verification_results_v2')
    op.drop_index('ix_verification_results_v2_label_created', table_name='verification_results_v2')
    op.drop_index(op.f('ix_verification_results_v2_final_label'), table_name='verification_results_v2')
    op.drop_index(op.f('ix_verification_results_v2_created_at'), table_name='verification_results_v2')
    op.drop_table('verification_results_v2')
    op.drop_index('ix_source_evidence_queries_submission_provider', table_name='source_evidence_queries')
    op.drop_index(op.f('ix_source_evidence_queries_submission_id'), table_name='source_evidence_queries')
    op.drop_index(op.f('ix_source_evidence_queries_search_provider'), table_name='source_evidence_queries')
    op.drop_index(op.f('ix_source_evidence_queries_executed_at'), table_name='source_evidence_queries')
    op.drop_table('source_evidence_queries')
    op.drop_index('uq_retrieved_articles_v2_submission_url_hash', table_name='retrieved_articles_v2')
    op.drop_index(op.f('ix_retrieved_articles_v2_submission_id'), table_name='retrieved_articles_v2')
    op.drop_index(op.f('ix_retrieved_articles_v2_rank_score'), table_name='retrieved_articles_v2')
    op.drop_index(op.f('ix_retrieved_articles_v2_extraction_success'), table_name='retrieved_articles_v2')
    op.drop_table('retrieved_articles_v2')
    op.drop_index(op.f('ix_ocr_extractions_submission_id'), table_name='ocr_extractions')
    op.drop_index(op.f('ix_ocr_extractions_created_at'), table_name='ocr_extractions')
    op.drop_table('ocr_extractions')
    op.drop_index(op.f('ix_multimodal_analysis_submission_id'), table_name='multimodal_analysis')
    op.drop_index(op.f('ix_multimodal_analysis_model_version'), table_name='multimodal_analysis')
    op.drop_index(op.f('ix_multimodal_analysis_created_at'), table_name='multimodal_analysis')
    op.drop_table('multimodal_analysis')
    op.drop_index(op.f('ix_expert_reviews_v2_submission_id'), table_name='expert_reviews_v2')
    op.drop_index(op.f('ix_expert_reviews_v2_status'), table_name='expert_reviews_v2')
    op.drop_index(op.f('ix_expert_reviews_v2_reviewer_id'), table_name='expert_reviews_v2')
    op.drop_index(op.f('ix_expert_reviews_v2_created_at'), table_name='expert_reviews_v2')
    op.drop_table('expert_reviews_v2')
    op.drop_index(op.f('ix_submissions_submitter_id'), table_name='submissions')
    op.drop_index(op.f('ix_submissions_submission_type'), table_name='submissions')
    op.drop_index('ix_submissions_status_created', table_name='submissions')
    op.drop_index(op.f('ix_submissions_status'), table_name='submissions')
    op.drop_index(op.f('ix_submissions_created_at'), table_name='submissions')
    op.drop_index(op.f('ix_submissions_content_hash'), table_name='submissions')
    op.drop_index(op.f('ix_submissions_claimed_source_id'), table_name='submissions')
    op.drop_table('submissions')
    op.drop_index(op.f('ix_expert_profiles_user_id'), table_name='expert_profiles')
    op.drop_index(op.f('ix_expert_profiles_created_at'), table_name='expert_profiles')
    op.drop_table('expert_profiles')
    op.drop_index(op.f('ix_credibility_weight_tiers_created_at'), table_name='credibility_weight_tiers')
    op.drop_table('credibility_weight_tiers')
    # op.drop_table() does not drop the native enum types it depends on — drop the
    # 3 enum types introduced by this migration explicitly (the 4 reused enum
    # types — verification_label_enum, query_type_enum, search_provider_enum,
    # extraction_method_enum — were created by earlier migrations and are left alone).
    postgresql.ENUM(name='submission_type_enum').drop(op.get_bind(), checkfirst=True)
    postgresql.ENUM(name='submission_status_enum').drop(op.get_bind(), checkfirst=True)
    postgresql.ENUM(name='multimodal_prediction_enum').drop(op.get_bind(), checkfirst=True)
