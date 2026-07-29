
revision = '3e7f64e4c47d'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

def upgrade() -> None:

    op.create_table('users',
    sa.Column('email', sa.String(length=255), nullable=False, comment='User email address — primary login credential'),
    sa.Column('hashed_password', sa.String(length=255), nullable=True, comment='Bcrypt-hashed password (NULL for OAuth-only accounts)'),
    sa.Column('full_name', sa.String(length=255), nullable=True),
    sa.Column('role', sa.String(length=50), nullable=False, comment='RBAC role: user | expert | admin'),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('is_verified', sa.Boolean(), nullable=False, comment='Email verification status'),
    sa.Column('oauth_provider', sa.String(length=50), nullable=True, comment='OAuth provider name: google | facebook | etc.'),
    sa.Column('oauth_subject', sa.String(length=255), nullable=True, comment='OAuth provider subject ID'),
    sa.Column('id', sa.UUID(), nullable=False, comment='Primary key — UUID v4 generated in Python before INSERT'),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False, comment='Row creation timestamp (UTC, set by DB on INSERT)'),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False, comment='Row last-update timestamp (UTC, auto-updated by DB on UPDATE)'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_users_created_at'), 'users', ['created_at'], unique=False)
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)
    op.create_index(op.f('ix_users_is_active'), 'users', ['is_active'], unique=False)
    op.create_index(op.f('ix_users_role'), 'users', ['role'], unique=False)
    op.create_table('credibility_scores',
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('score', sa.Float(), nullable=False, comment='Current credibility score [0.0 – 1.0]'),
    sa.Column('total_votes', sa.Integer(), nullable=False, comment='Total number of finalized votes by this expert'),
    sa.Column('correct_votes', sa.Integer(), nullable=False, comment='Number of votes that matched the final verdict'),
    sa.Column('id', sa.UUID(), nullable=False, comment='Primary key — UUID v4 generated in Python before INSERT'),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False, comment='Row creation timestamp (UTC, set by DB on INSERT)'),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False, comment='Row last-update timestamp (UTC, auto-updated by DB on UPDATE)'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_credibility_scores_created_at'), 'credibility_scores', ['created_at'], unique=False)
    op.create_index(op.f('ix_credibility_scores_user_id'), 'credibility_scores', ['user_id'], unique=True)
    op.create_table('notifications',
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('title', sa.String(length=255), nullable=False),
    sa.Column('body', sa.Text(), nullable=False),
    sa.Column('notification_type', sa.String(length=50), nullable=False),
    sa.Column('link_url', sa.String(length=512), nullable=True, comment='Deep-link to the relevant result page'),
    sa.Column('is_read', sa.Boolean(), nullable=False),
    sa.Column('id', sa.UUID(), nullable=False, comment='Primary key — UUID v4 generated in Python before INSERT'),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False, comment='Row creation timestamp (UTC, set by DB on INSERT)'),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False, comment='Row last-update timestamp (UTC, auto-updated by DB on UPDATE)'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_notifications_created_at'), 'notifications', ['created_at'], unique=False)
    op.create_index(op.f('ix_notifications_is_read'), 'notifications', ['is_read'], unique=False)
    op.create_index(op.f('ix_notifications_notification_type'), 'notifications', ['notification_type'], unique=False)
    op.create_index(op.f('ix_notifications_user_id'), 'notifications', ['user_id'], unique=False)
    op.create_table('password_reset_tokens',
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('token_hash', sa.String(length=64), nullable=False),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('used', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('id', sa.UUID(), nullable=False, comment='Primary key — UUID v4 generated in Python before INSERT'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('token_hash')
    )
    op.create_index(op.f('ix_password_reset_tokens_user_id'), 'password_reset_tokens', ['user_id'], unique=False)
    op.create_table('refresh_tokens',
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('token_hash', sa.String(length=64), nullable=False, comment='SHA-256 hash of the refresh token'),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('revoked', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('id', sa.UUID(), nullable=False, comment='Primary key — UUID v4 generated in Python before INSERT'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('token_hash')
    )
    op.create_index(op.f('ix_refresh_tokens_revoked'), 'refresh_tokens', ['revoked'], unique=False)
    op.create_index(op.f('ix_refresh_tokens_user_id'), 'refresh_tokens', ['user_id'], unique=False)
    op.create_table('user_profiles',
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('bio', sa.Text(), nullable=True),
    sa.Column('avatar_url', sa.String(length=512), nullable=True),
    sa.Column('verification_count', sa.Integer(), nullable=False),
    sa.Column('id', sa.UUID(), nullable=False, comment='Primary key — UUID v4 generated in Python before INSERT'),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False, comment='Row creation timestamp (UTC, set by DB on INSERT)'),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False, comment='Row last-update timestamp (UTC, auto-updated by DB on UPDATE)'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_user_profiles_created_at'), 'user_profiles', ['created_at'], unique=False)
    op.create_index(op.f('ix_user_profiles_user_id'), 'user_profiles', ['user_id'], unique=True)
    op.create_table('expert_reviews',
    sa.Column('claim_id', sa.UUID(), nullable=False),
    sa.Column('reviewer_id', sa.UUID(), nullable=True),
    sa.Column('ai_label', postgresql.ENUM('TRUE', 'FALSE', 'PARTIALLY_TRUE', 'NOT_FOUND_IN_CLAIMED_SOURCE', name='verification_label_enum', create_type=False), nullable=False, comment='Original AI verdict at time of review'),
    sa.Column('expert_label', postgresql.ENUM('TRUE', 'FALSE', 'PARTIALLY_TRUE', 'NOT_FOUND_IN_CLAIMED_SOURCE', name='verification_label_enum', create_type=False), nullable=False, comment="Expert's verdict"),
    sa.Column('justification', sa.Text(), nullable=True, comment="Expert's written justification (min 50 chars)"),
    sa.Column('credibility_weight', sa.Float(), nullable=False, comment="Expert's credibility score at the time of voting"),
    sa.Column('status', sa.String(length=50), nullable=False, comment='Review status: pending | finalized'),
    sa.Column('id', sa.UUID(), nullable=False, comment='Primary key — UUID v4 generated in Python before INSERT'),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False, comment='Row creation timestamp (UTC, set by DB on INSERT)'),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False, comment='Row last-update timestamp (UTC, auto-updated by DB on UPDATE)'),
    sa.ForeignKeyConstraint(['claim_id'], ['verified_claims.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['reviewer_id'], ['users.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_expert_reviews_claim_id'), 'expert_reviews', ['claim_id'], unique=False)
    op.create_index(op.f('ix_expert_reviews_created_at'), 'expert_reviews', ['created_at'], unique=False)
    op.create_index(op.f('ix_expert_reviews_reviewer_id'), 'expert_reviews', ['reviewer_id'], unique=False)
    op.create_index(op.f('ix_expert_reviews_status'), 'expert_reviews', ['status'], unique=False)
    op.create_table('user_feedback',
    sa.Column('claim_id', sa.UUID(), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=True),
    sa.Column('rating', sa.Integer(), nullable=True, comment='User rating 1-5'),
    sa.Column('feedback_type', sa.String(length=50), nullable=False, comment='agree | disagree | unclear | other'),
    sa.Column('comment', sa.Text(), nullable=True),
    sa.Column('id', sa.UUID(), nullable=False, comment='Primary key — UUID v4 generated in Python before INSERT'),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False, comment='Row creation timestamp (UTC, set by DB on INSERT)'),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False, comment='Row last-update timestamp (UTC, auto-updated by DB on UPDATE)'),
    sa.ForeignKeyConstraint(['claim_id'], ['verified_claims.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_user_feedback_claim_id'), 'user_feedback', ['claim_id'], unique=False)
    op.create_index(op.f('ix_user_feedback_created_at'), 'user_feedback', ['created_at'], unique=False)
    op.create_index(op.f('ix_user_feedback_user_id'), 'user_feedback', ['user_id'], unique=False)
    op.alter_column('multimodal_predictions', 'confidence_fake',
               existing_type=sa.DOUBLE_PRECISION(precision=53),
               comment='Softmax probability for the FAKE class (0.0–1.0)',
               existing_comment='Softmax probability for the FAKE class (0.0-1.0)',
               existing_nullable=False)
    op.alter_column('multimodal_predictions', 'confidence_real',
               existing_type=sa.DOUBLE_PRECISION(precision=53),
               comment='Softmax probability for the NON_FAKE class (0.0–1.0)',
               existing_comment='Softmax probability for the NON_FAKE class (0.0-1.0)',
               existing_nullable=False)
    op.alter_column('search_queries', 'search_provider',
               existing_type=postgresql.ENUM('BRAVE', 'GOOGLE_RSS', 'DDG', 'SEARXNG', 'NEWSDATA', 'GOOGLE_CUSTOM_SEARCH', 'PY_GOOGLE_NEWS', name='search_provider_enum'),
               comment='Which search provider executed this query: google_rss | ddg',
               existing_comment='Which search provider executed this query: brave | google_rss | ddg',
               existing_nullable=False)
    op.alter_column('verification_logs', 'metadata',
               existing_type=postgresql.JSONB(astext_type=sa.Text()),
               comment='Stage-specific debug payload as JSONB',
               existing_comment='Stage-specific debug payload as JSONB (e.g. query text, error message, scores)',
               existing_nullable=True)
    op.add_column('verified_claims', sa.Column('submitter_id', sa.UUID(), nullable=True, comment='FK to users.id — NULL for anonymous submissions'))
    op.alter_column('verified_claims', 'source_id',
               existing_type=sa.UUID(),
               comment='FK to verified_sources.id — set when source is successfully resolved',
               existing_comment='FK to source_registry.id — set when source is successfully resolved',
               existing_nullable=True)
    op.create_index(op.f('ix_verified_claims_submitter_id'), 'verified_claims', ['submitter_id'], unique=False)
    op.create_foreign_key(None, 'verified_claims', 'users', ['submitter_id'], ['id'], ondelete='SET NULL')
    op.alter_column('verified_sources', 'body_selectors',
               existing_type=postgresql.JSONB(astext_type=sa.Text()),
               comment='CSS selectors for extracting article body',
               existing_nullable=True)
    op.alter_column('verified_sources', 'title_selectors',
               existing_type=postgresql.JSONB(astext_type=sa.Text()),
               comment='CSS selectors for extracting article title',
               existing_nullable=True)
    op.alter_column('verified_sources', 'date_selectors',
               existing_type=postgresql.JSONB(astext_type=sa.Text()),
               comment='CSS selectors for extracting published date',
               existing_nullable=True)
    op.alter_column('verified_sources', 'internal_search_url',
               existing_type=sa.VARCHAR(length=512),
               comment='URL template for internal site search (e.g. .../search?q={query})',
               existing_nullable=True)
    op.alter_column('verified_sources', 'article_url_patterns',
               existing_type=postgresql.JSONB(astext_type=sa.Text()),
               comment='Regex patterns to match valid article URLs',
               existing_nullable=True)



def downgrade() -> None:

    op.alter_column('verified_sources', 'article_url_patterns',
               existing_type=postgresql.JSONB(astext_type=sa.Text()),
               comment=None,
               existing_comment='Regex patterns to match valid article URLs',
               existing_nullable=True)
    op.alter_column('verified_sources', 'internal_search_url',
               existing_type=sa.VARCHAR(length=512),
               comment=None,
               existing_comment='URL template for internal site search (e.g. .../search?q={query})',
               existing_nullable=True)
    op.alter_column('verified_sources', 'date_selectors',
               existing_type=postgresql.JSONB(astext_type=sa.Text()),
               comment=None,
               existing_comment='CSS selectors for extracting published date',
               existing_nullable=True)
    op.alter_column('verified_sources', 'title_selectors',
               existing_type=postgresql.JSONB(astext_type=sa.Text()),
               comment=None,
               existing_comment='CSS selectors for extracting article title',
               existing_nullable=True)
    op.alter_column('verified_sources', 'body_selectors',
               existing_type=postgresql.JSONB(astext_type=sa.Text()),
               comment=None,
               existing_comment='CSS selectors for extracting article body',
               existing_nullable=True)
    op.drop_constraint(None, 'verified_claims', type_='foreignkey')
    op.drop_index(op.f('ix_verified_claims_submitter_id'), table_name='verified_claims')
    op.alter_column('verified_claims', 'source_id',
               existing_type=sa.UUID(),
               comment='FK to source_registry.id — set when source is successfully resolved',
               existing_comment='FK to verified_sources.id — set when source is successfully resolved',
               existing_nullable=True)
    op.drop_column('verified_claims', 'submitter_id')
    op.alter_column('verification_logs', 'metadata',
               existing_type=postgresql.JSONB(astext_type=sa.Text()),
               comment='Stage-specific debug payload as JSONB (e.g. query text, error message, scores)',
               existing_comment='Stage-specific debug payload as JSONB',
               existing_nullable=True)
    op.alter_column('search_queries', 'search_provider',
               existing_type=postgresql.ENUM('BRAVE', 'GOOGLE_RSS', 'DDG', 'SEARXNG', 'NEWSDATA', 'GOOGLE_CUSTOM_SEARCH', 'PY_GOOGLE_NEWS', name='search_provider_enum'),
               comment='Which search provider executed this query: brave | google_rss | ddg',
               existing_comment='Which search provider executed this query: google_rss | ddg',
               existing_nullable=False)
    op.alter_column('multimodal_predictions', 'confidence_real',
               existing_type=sa.DOUBLE_PRECISION(precision=53),
               comment='Softmax probability for the NON_FAKE class (0.0-1.0)',
               existing_comment='Softmax probability for the NON_FAKE class (0.0–1.0)',
               existing_nullable=False)
    op.alter_column('multimodal_predictions', 'confidence_fake',
               existing_type=sa.DOUBLE_PRECISION(precision=53),
               comment='Softmax probability for the FAKE class (0.0-1.0)',
               existing_comment='Softmax probability for the FAKE class (0.0–1.0)',
               existing_nullable=False)
    op.drop_index(op.f('ix_user_feedback_user_id'), table_name='user_feedback')
    op.drop_index(op.f('ix_user_feedback_created_at'), table_name='user_feedback')
    op.drop_index(op.f('ix_user_feedback_claim_id'), table_name='user_feedback')
    op.drop_table('user_feedback')
    op.drop_index(op.f('ix_expert_reviews_status'), table_name='expert_reviews')
    op.drop_index(op.f('ix_expert_reviews_reviewer_id'), table_name='expert_reviews')
    op.drop_index(op.f('ix_expert_reviews_created_at'), table_name='expert_reviews')
    op.drop_index(op.f('ix_expert_reviews_claim_id'), table_name='expert_reviews')
    op.drop_table('expert_reviews')
    op.drop_index(op.f('ix_user_profiles_user_id'), table_name='user_profiles')
    op.drop_index(op.f('ix_user_profiles_created_at'), table_name='user_profiles')
    op.drop_table('user_profiles')
    op.drop_index(op.f('ix_refresh_tokens_user_id'), table_name='refresh_tokens')
    op.drop_index(op.f('ix_refresh_tokens_revoked'), table_name='refresh_tokens')
    op.drop_table('refresh_tokens')
    op.drop_index(op.f('ix_password_reset_tokens_user_id'), table_name='password_reset_tokens')
    op.drop_table('password_reset_tokens')
    op.drop_index(op.f('ix_notifications_user_id'), table_name='notifications')
    op.drop_index(op.f('ix_notifications_notification_type'), table_name='notifications')
    op.drop_index(op.f('ix_notifications_is_read'), table_name='notifications')
    op.drop_index(op.f('ix_notifications_created_at'), table_name='notifications')
    op.drop_table('notifications')
    op.drop_index(op.f('ix_credibility_scores_user_id'), table_name='credibility_scores')
    op.drop_index(op.f('ix_credibility_scores_created_at'), table_name='credibility_scores')
    op.drop_table('credibility_scores')
    op.drop_index(op.f('ix_users_role'), table_name='users')
    op.drop_index(op.f('ix_users_is_active'), table_name='users')
    op.drop_index(op.f('ix_users_email'), table_name='users')
    op.drop_index(op.f('ix_users_created_at'), table_name='users')
    op.drop_table('users')

