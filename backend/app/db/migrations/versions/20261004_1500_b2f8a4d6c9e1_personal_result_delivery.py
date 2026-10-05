"""Uncalculated expert credibility and durable personal result delivery."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = 'b2f8a4d6c9e1'
down_revision = 'a6d9e2f4b8c0'
branch_labels = None
depends_on = None


def upgrade():
    # Earlier voting code introduced ESCALATED without updating PostgreSQL's
    # enum. Commit this additive change before queries use the new enum value.
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE submission_status_enum ADD VALUE IF NOT EXISTS 'ESCALATED'")
    op.alter_column('expert_profiles', 'credibility_score', existing_type=sa.Float(), nullable=True, server_default=None)
    op.execute("""UPDATE expert_profiles SET credibility_score = CASE
        WHEN total_votes > 0 AND total_votes >= COALESCE((SELECT activation_threshold_votes FROM voting_config ORDER BY created_at LIMIT 1), 10)
        THEN ROUND(correct_votes::numeric / total_votes, 4) ELSE NULL END""")
    op.create_table('result_deliveries',
        sa.Column('submission_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('submissions.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('stage', sa.String(20), primary_key=True),
        sa.Column('verdict', sa.String(20), nullable=True),
        sa.Column('email_status', sa.String(20), nullable=False),
        sa.Column('email_attempts', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('next_attempt_at', sa.DateTime(timezone=True)),
        sa.Column('sent_at', sa.DateTime(timezone=True)),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index('ix_result_deliveries_email_status', 'result_deliveries', ['email_status'])
    op.create_index('ix_result_deliveries_created_at', 'result_deliveries', ['created_at'])
    # Mark existing stages handled: deployment must not email historical results.
    for stage in ('preliminary', 'final'):
        condition = 'AND COALESCE(o.overall_verdict, v.overall_verdict, m.expert_overall_verdict) IS NOT NULL' if stage == 'final' else ''
        op.execute(sa.text(f"""INSERT INTO result_deliveries (submission_id, stage, email_status)
            SELECT s.id, '{stage}', 'historical' FROM submissions s
            LEFT JOIN verification_results v ON v.submission_id = s.id
            LEFT JOIN verification_results o ON o.submission_id = v.reused_from_submission_id
            LEFT JOIN multimodal_analysis m ON m.submission_id = s.id
            WHERE s.submitter_id IS NOT NULL AND s.status IN ('EXPERT_REVIEW', 'FINALIZED', 'ESCALATED')
            AND (v.source_status IS NOT NULL OR m.id IS NOT NULL) {condition}"""))


def downgrade():
    # PostgreSQL enum values are intentionally retained on downgrade: removing
    # ESCALATED would require rewriting existing submissions and their type.
    op.drop_table('result_deliveries')
    op.execute('UPDATE expert_profiles SET credibility_score = 0.5 WHERE credibility_score IS NULL')
    op.alter_column('expert_profiles', 'credibility_score', existing_type=sa.Float(), nullable=False)
